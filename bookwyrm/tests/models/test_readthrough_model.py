""" testing models """
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bookwyrm import models


class ReadThroughTestBase(TestCase):
    """create user and book for ReadThrough tests"""

    def setUp(self):
        """look, a shelf"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )

        self.work = models.Work.objects.create(title="Example Work")
        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )


class ReadThroughConstraints(ReadThroughTestBase):
    def _assert_create(self, start_date, finish_date=None, /, read_status="read"):
        """create ReadThrough helper"""
        self.assertIsNotNone(
            models.ReadThrough.objects.create(
                user=self.user,
                book=self.edition,
                start_date=start_date,
                finish_date=finish_date,
                read_status=read_status,
            )
        )

    def _fail_create(self, start_date, finish_date, /, read_status):
        """expected failure in ReadThrough creation"""
        with self.assertRaises(IntegrityError):
            self._assert_create(start_date, finish_date, read_status)

    def test_valid_dates(self):
        """valid combinations of start_date and finish_date"""
        start = timezone.now()

        self._assert_create(None, None)
        self._assert_create(start, None)
        self._assert_create(None, start)
        self._assert_create(start, start + timedelta(days=1))
        self._assert_create(start, start)

        self._assert_create(None, None, "to-read")
        self._assert_create(None, None, "reading")
        self._assert_create(start, None, "reading")

    def test_chronology_constraint(self):
        """finish_date >= start_date"""
        start = timezone.now()
        before_start = start - timedelta(days=2)

        self._fail_create(start, before_start, "read")

    def test_currently_reading_constraint(self):
        """no finish date allowed for `reading`"""
        start = finish = timezone.now()
        self._fail_create(start, finish, "reading")

    def test_to_read_constraint(self):
        """no dates allowed for `to-read`"""
        start = finish = timezone.now()
        test_cases = [
            ("start date", start, None),
            ("finish date", None, start),
            ("start and finish", start, finish),
        ]
        for desc, beg, end in test_cases:
            with self.subTest(desc), transaction.atomic():
                self._fail_create(beg, end, "to-read")


class ReadThroughProgressUpdates(ReadThroughTestBase):
    """test ProgressUpdate creation from ReadThrough objects"""

    def test_progress_update(self):
        """Test progress updates"""
        readthrough = models.ReadThrough.objects.create(
            user=self.user, book=self.edition
        )

        readthrough.create_update()  # No-op, no progress yet
        readthrough.progress = 10
        readthrough.create_update()
        readthrough.progress = 20
        readthrough.progress_mode = models.ProgressMode.PERCENT
        readthrough.create_update()

        updates = readthrough.progressupdate_set.order_by("created_date").all()
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].progress, 10)
        self.assertEqual(updates[0].mode, models.ProgressMode.PAGE)
        self.assertEqual(updates[1].progress, 20)
        self.assertEqual(updates[1].mode, models.ProgressMode.PERCENT)

        readthrough.progress = -10
        self.assertRaises(ValidationError, readthrough.clean_fields)
        update = readthrough.create_update()
        self.assertRaises(ValidationError, update.clean_fields)
