""" testing import """
import pathlib
import datetime

from django.test import TestCase

from bookwyrm import models
from bookwyrm.importers import GoodreadsImporter
from bookwyrm.models.import_job import handle_imported_book


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


class GoodreadsImport(TestCase):
    """importing from goodreads csv"""

    def setUp(self):
        """use a test csv"""
        self.importer = GoodreadsImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/goodreads.csv")
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

        import_items = (
            models.ImportItem.objects.filter(job=import_job).all().order_by("id")
        )
        self.assertEqual(len(import_items), 3)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["Book Id"], "42036538")
        self.assertEqual(import_items[0].normalized_data["isbn_13"], '="9781250313195"')
        self.assertEqual(import_items[0].normalized_data["isbn_10"], '="1250313198"')
        self.assertEqual(import_items[0].normalized_data["goodreads_key"], "42036538")

        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data["Book Id"], "52691223")
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].data["Book Id"], "28694510")

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
        self.assertEqual(retry_items[0].data["Book Id"], "42036538")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data["Book Id"], "52691223")

    def test_handle_imported_book(self):
        """goodreads import added a book, this adds related connections"""
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
        self.assertEqual(
            shelf.shelfbook_set.first().shelved_date, make_date(2020, 10, 21)
        )

        readthrough = models.ReadThrough.objects.get(user=self.local_user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date, make_date(2020, 10, 21))
        self.assertEqual(readthrough.finish_date, make_date(2020, 10, 25))

    def test_handle_imported_book_review(self):
        """goodreads review import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.get(index=2)
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        review = models.Review.objects.get(book=self.book, user=self.local_user)
        self.assertEqual(review.content, "mixed feelings")
        self.assertEqual(review.rating, 2)
        self.assertEqual(review.published_date, make_date(2019, 7, 8))
        self.assertEqual(review.privacy, "unlisted")

    def test_handle_imported_book_rating(self):
        """goodreads rating import"""
        import_job = self.importer.create_job(
            self.local_user, self.csv, True, "unlisted"
        )
        import_item = import_job.items.filter(index=0).first()
        import_item.book = self.book
        import_item.save()

        handle_imported_book(import_item)

        review = models.ReviewRating.objects.get(book=self.book, user=self.local_user)
        self.assertIsInstance(review, models.ReviewRating)
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.published_date, make_date(2020, 10, 25))
        self.assertEqual(review.privacy, "unlisted")
