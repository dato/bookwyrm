""" testing import """
from collections import namedtuple
import pathlib
import io
from unittest.mock import patch
import datetime

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.importers import Importer
from bookwyrm.models.import_job import start_import_task, import_item_task
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


class GenericImporter(TestCase):
    """importing from csv"""

    def setUp(self):
        """use a test csv"""
        self.importer = Importer()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/generic.csv")
        # pylint: disable-next=consider-using-with
        self.csv = open(datafile, "r", encoding=self.importer.encoding)

    def tearDown(self):
        """close test csv"""
        self.csv.close()

    @classmethod
    def setUpTestData(cls):
        """populate database"""
        cls.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True
        )
        models.SiteSettings.objects.create()
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_create_job(self):
        """creates the import job entry and checks csv"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        self.assertEqual(import_job.user, self.local_user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, "public")

        import_items = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")
        )
        self.assertEqual(len(import_items), 4)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].normalized_data["id"], "38")
        self.assertEqual(import_items[0].normalized_data["title"], "Gideon the Ninth")
        self.assertEqual(import_items[0].normalized_data["authors"], "Tamsyn Muir")
        self.assertEqual(import_items[0].normalized_data["isbn_13"], "9781250313195")
        self.assertIsNone(import_items[0].normalized_data["isbn_10"])
        self.assertEqual(import_items[0].normalized_data["shelf"], "read")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].normalized_data["id"], "48")
        self.assertEqual(import_items[1].normalized_data["title"], "Harrow the Ninth")

        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].normalized_data["id"], "23")
        self.assertEqual(import_items[2].normalized_data["title"], "Subcutanean")

        self.assertEqual(import_items[3].index, 3)
        self.assertEqual(import_items[3].normalized_data["id"], "10")
        self.assertEqual(import_items[3].normalized_data["title"], "Patisserie at Home")

    def test_create_retry_job(self):
        """trying again with items that didn't import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_items = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")[:2]
        )

        retry = self.importer.create_retry_job(
            self.local_user, import_job, import_items
        )
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.local_user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, "unlisted")

        retry_items = models.ImportItem.objects.filter(job=retry).all().order_by("id")
        self.assertEqual(len(retry_items), 2)
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(retry_items[0].normalized_data["id"], "38")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].normalized_data["id"], "48")

    def test_start_import(self):
        """check that a task was created"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        MockTask = namedtuple("Task", ("id"))

        with patch("bookwyrm.models.import_job.start_import_task.delay") as mock:
            mock.return_value = MockTask(123)
            import_job.start_job()

        self.assertEqual(mock.call_count, 1)
        import_job.refresh_from_db()
        self.assertEqual(import_job.task_id, "123")

    @responses.activate
    def test_start_import_task(self):
        """resolve entry"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        MockTask = namedtuple("Task", ("id"))

        with patch("bookwyrm.models.import_job.import_item_task.delay") as mock:
            mock.return_value = MockTask(123)
            start_import_task(import_job.id)

        self.assertEqual(mock.call_count, 4)

    @responses.activate
    def test_import_item_task(self):
        """resolve entry"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_item = models.ImportItem.objects.get(job=import_job, index=0)

        with (
            patch(
                "bookwyrm.models.import_job.ImportItem.get_book_from_identifier"
            ) as resolve,
            patch(
                "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
            ) as mock,
        ):
            resolve.return_value = self.book
            import_item_task(import_item.id)
            kwargs = mock.call_args.kwargs

        self.assertEqual(kwargs["queue"], "import_triggered")
        import_item.refresh_from_db()

    def test_complete_job(self):
        """test notification"""

        # csv content not important
        csv = io.StringIO("title,author_text,remote_id\nbeep,boop,blurp")
        import_job = self.importer.create_job(self.local_user, csv, False, "unlisted")
        items = import_job.items.all()
        item = items.last()
        item.fail_reason = "hello"
        item.save()
        item.update_job()
        import_job.refresh_from_db()
        self.assertTrue(import_job.complete)
        self.assertTrue(
            models.Notification.objects.filter(
                user=self.local_user,
                related_import=import_job,
                notification_type="IMPORT",
            ).exists()
        )

    def test_handle_imported_book(self):
        """import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
        ).first()
        self.assertIsNone(shelf.books.first())

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

    def test_handle_imported_book_already_shelved(self):
        """import added a book, this adds related connections"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.TO_READ
        ).first()
        models.ShelfBook.objects.create(
            shelf=shelf,
            user=self.local_user,
            book=self.book,
            shelved_date=make_date(2020, 2, 2),
        )
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(
            shelf.shelfbook_set.first().shelved_date, make_date(2020, 2, 2)
        )
        self.assertIsNone(
            self.local_user.shelf_set.get(
                identifier=models.Shelf.READ_FINISHED
            ).books.first()
        )

    def test_handle_import_twice(self):
        """re-importing books"""
        shelf = self.local_user.shelf_set.filter(
            identifier=models.Shelf.READ_FINISHED
        ).first()
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_item = import_job.items.first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)
        handle_imported_book(import_item)

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertEqual(models.ReadThrough.objects.count(), 1)

    def test_handle_imported_book_review(self):
        """review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=3).first()
        import_item.book = self.book
        import_item.save()

        with patch("bookwyrm.models.Status.broadcast") as broadcast_mock:
            handle_imported_book(import_item)

        kwargs = broadcast_mock.call_args.kwargs
        self.assertEqual(kwargs["software"], "bookwyrm")
        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.content, "mixed feelings")
        self.assertEqual(review.rating, 2.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review, review)

    def test_handle_imported_book_rating(self):
        """rating import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    def test_handle_imported_book_rating_duplicate_with_link(self):
        """rating import twice"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)
        handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    def test_handle_imported_book_rating_duplicate_without_link(self):
        """rating import twice"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=1).first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        import_item.refresh_from_db()
        import_item.linked_review = None
        import_item.save()

        handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3.0)
        self.assertEqual(review.privacy, "unlisted")

        import_item.refresh_from_db()
        self.assertEqual(import_item.linked_review.id, review.id)

    def test_handle_imported_book_reviews_disabled(self):
        """review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "unlisted"
        )
        import_item = import_job.items.filter(index=3).first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        self.assertFalse(
            models.Review.objects.filter(book=self.book, user=self.local_user).exists()
        )

    def test_import_limit(self):
        """checks if import limit works"""
        site_settings = models.SiteSettings.objects.get()
        site_settings.import_size_limit = 2
        site_settings.import_limit_reset = 2
        site_settings.save()

        import_job = self.importer.create_job(
            self.local_user, self.csv, False, "public"
        )
        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 2)
