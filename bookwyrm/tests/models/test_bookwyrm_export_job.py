"""test bookwyrm user export functions"""
import datetime
import json
import pathlib


from django.utils import timezone
from django.test import TestCase

from bookwyrm import models
from bookwyrm.utils.tar import BookwyrmTarFile


class BookwyrmExportJob(TestCase):
    """testing user export functions"""

    @classmethod
    def setUpTestData(cls):
        """lots of stuff to set up for a user export"""
        cls.local_user = models.User.objects.create_user(
            "mouse",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
            name="Mouse",
            summary="I'm a real bookmouse",
            manually_approves_followers=False,
            hide_follows=False,
            show_goal=False,
            show_suggested_users=False,
            discoverable=True,
            preferred_timezone="America/Los Angeles",
            default_post_privacy="followers",
        )
        avatar_path = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        with open(avatar_path, "rb") as avatar_file:
            cls.local_user.avatar.save("mouse-avatar.jpg", avatar_file)

        cls.rat_user = models.User.objects.create_user(
            "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
        )

        cls.badger_user = models.User.objects.create_user(
            "badger",
            "badger@badger.badger",
            "badgerword",
            local=True,
            localname="badger",
        )

        models.AnnualGoal.objects.create(
            user=cls.local_user,
            year=timezone.now().year,
            goal=128937123,
            privacy="followers",
        )

        cls.list = models.List.objects.create(
            name="My excellent list",
            user=cls.local_user,
            remote_id="https://local.lists/1111",
        )

        cls.saved_list = models.List.objects.create(
            name="My cool list",
            user=cls.rat_user,
            remote_id="https://local.lists/9999",
        )

        cls.local_user.saved_lists.add(cls.saved_list)
        cls.local_user.blocks.add(cls.badger_user)
        cls.rat_user.followers.add(cls.local_user)

        # book, edition, author
        cls.author = models.Author.objects.create(name="Sam Zhu")
        cls.work = models.Work.objects.create(
            title="Example Work", remote_id="https://example.com/book/1"
        )
        cls.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=cls.work
        )

        # edition cover
        cover_path = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        with open(cover_path, "rb") as cover_file:
            cls.edition.cover.save("tèst.jpg", cover_file)

        cls.edition.authors.add(cls.author)

        # readthrough
        cls.readthrough_start = timezone.now()
        finish = cls.readthrough_start + datetime.timedelta(days=1)
        models.ReadThrough.objects.create(
            user=cls.local_user,
            book=cls.edition,
            start_date=cls.readthrough_start,
            finish_date=finish,
        )

        # shelve
        read_shelf = models.Shelf.objects.get(user=cls.local_user, identifier="read")
        models.ShelfBook.objects.create(
            book=cls.edition, shelf=read_shelf, user=cls.local_user
        )

        # add to list
        models.ListItem.objects.create(
            book_list=cls.list,
            user=cls.local_user,
            book=cls.edition,
            approved=True,
            order=1,
        )

        # review
        models.Review.objects.create(
            content="awesome",
            name="my review",
            rating=5,
            user=cls.local_user,
            book=cls.edition,
        )
        # comment
        models.Comment.objects.create(
            content="ok so far",
            user=cls.local_user,
            book=cls.edition,
            progress=15,
        )
        # deleted comment
        models.Comment.objects.create(
            content="so far",
            user=cls.local_user,
            book=cls.edition,
            progress=5,
            deleted=True,
        )
        # quote
        models.Quotation.objects.create(
            content="check this out",
            quote="A rose by any other name",
            user=cls.local_user,
            book=cls.edition,
        )
        # deleted quote
        models.Quotation.objects.create(
            content="check this out",
            quote="A rose by any other name",
            user=cls.local_user,
            book=cls.edition,
            deleted=True,
        )

        cls.job = models.BookwyrmExportJob.objects.create(user=cls.local_user)

        # run the first stage of the export
        models.bookwyrm_export_job.create_export_json_task(job_id=cls.job.id)
        cls.job.refresh_from_db()

    def test_add_book_to_user_export_job(self):
        """does AddBookToUserExportJob ...add the book to the export?"""
        self.assertIsNotNone(self.job.export_json["books"])
        self.assertEqual(len(self.job.export_json["books"]), 1)
        book = self.job.export_json["books"][0]

        self.assertEqual(book["work"]["id"], self.work.remote_id)
        self.assertEqual(len(book["authors"]), 1)
        self.assertEqual(len(book["shelves"]), 1)
        self.assertEqual(len(book["lists"]), 1)
        self.assertEqual(len(book["comments"]), 1)
        self.assertEqual(len(book["reviews"]), 1)
        self.assertEqual(len(book["quotations"]), 1)
        self.assertEqual(len(book["readthroughs"]), 1)

        self.assertEqual(book["edition"]["id"], self.edition.remote_id)
        self.assertEqual(
            book["edition"]["cover"]["url"], f"images/{self.edition.cover.name}"
        )

    def test_start_export_task(self):
        """test saved list task saves initial json and data"""
        self.assertIsNotNone(self.job.export_data)
        self.assertIsNotNone(self.job.export_json)
        self.assertEqual(self.job.export_json["name"], self.local_user.name)

    def test_export_saved_lists_task(self):
        """test export_saved_lists_task adds the saved lists"""
        self.assertIsNotNone(self.job.export_json["saved_lists"])
        self.assertEqual(
            self.job.export_json["saved_lists"][0], self.saved_list.remote_id
        )

    def test_export_follows_task(self):
        """test export_follows_task adds the follows"""
        self.assertIsNotNone(self.job.export_json["follows"])
        self.assertEqual(self.job.export_json["follows"][0], self.rat_user.remote_id)

    def test_export_blocks_task(self):
        """test export_blocks_task adds the blocks"""
        self.assertIsNotNone(self.job.export_json["blocks"])
        self.assertEqual(self.job.export_json["blocks"][0], self.badger_user.remote_id)

    def test_export_reading_goals_task(self):
        """test export_reading_goals_task adds the goals"""
        self.assertIsNotNone(self.job.export_json["goals"])
        self.assertEqual(self.job.export_json["goals"][0]["goal"], 128937123)

    def test_json_export(self):
        """test json_export job adds settings"""
        self.assertIsNotNone(self.job.export_json["settings"])
        self.assertFalse(self.job.export_json["settings"]["show_goal"])
        self.assertEqual(
            self.job.export_json["settings"]["preferred_timezone"],
            "America/Los Angeles",
        )
        self.assertEqual(
            self.job.export_json["settings"]["default_post_privacy"], "followers"
        )
        self.assertFalse(self.job.export_json["settings"]["show_suggested_users"])

    def test_get_books_for_user(self):
        """does get_books_for_user get all the books"""

        data = models.bookwyrm_export_job.get_books_for_user(self.local_user)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].title, "Example Edition")

    def test_archive(self):
        """actually create the TAR file"""
        models.bookwyrm_export_job.create_archive_task(job_id=self.job.id)
        self.job.refresh_from_db()

        with (
            self.job.export_data.open("rb") as tar_file,
            BookwyrmTarFile.open(mode="r", fileobj=tar_file) as tar,
        ):
            archive_json_file = tar.extractfile("archive.json")
            data = json.load(archive_json_file)

            # JSON from the archive should be what we want it to be
            self.assertEqual(data, self.job.export_json)

            # User avatar should be present in archive
            with self.local_user.avatar.open() as expected_avatar:
                archive_avatar = tar.extractfile(data["icon"]["url"])
                self.assertEqual(expected_avatar.read(), archive_avatar.read())
