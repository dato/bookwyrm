""" testing activitystreams """
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookwyrm import activitystreams, models


class ActivitystreamsSignals(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """use a test csv"""
        cls.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        cls.remote_user = models.User.objects.create_user(
            "rat",
            "rat@rat.com",
            "ratword",
            local=False,
            remote_id="https://example.com/users/rat",
            inbox="https://example.com/users/rat/inbox",
            outbox="https://example.com/users/rat/outbox",
        )

    def test_add_status_on_create_ignore(self):
        """a new statuses has entered"""
        activitystreams.add_status_on_create(models.User, self.local_user, False)

    def test_add_status_on_create_deleted(self):
        """a new statuses has entered"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public", deleted=True
        )
        with patch("bookwyrm.activitystreams.remove_status_task.delay") as mock:
            activitystreams.add_status_on_create(models.Status, status, False)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], status.id)

    def test_add_status_on_create_created(self):
        """a new statuses has entered"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "streams")

    def test_add_status_on_create_created_low_priority(self):
        """a new statuses has entered"""
        # created later than publication
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="public",
            created_date=datetime.datetime(2022, 5, 16, tzinfo=datetime.timezone.utc),
            published_date=datetime.datetime(2022, 5, 14, tzinfo=datetime.timezone.utc),
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)

        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "import_triggered")

        # published later than yesterday
        status = models.Status.objects.create(
            user=self.remote_user,
            content="hi",
            privacy="public",
            published_date=timezone.now() - datetime.timedelta(days=1),
        )
        with patch("bookwyrm.activitystreams.add_status_task.apply_async") as mock:
            activitystreams.add_status_on_create_command(models.Status, status, False)

        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[1]
        self.assertEqual(args["args"][0], status.id)
        self.assertEqual(args["queue"], "import_triggered")

    def test_populate_streams_on_account_create_command(self):
        """create streams for a user"""
        with patch("bookwyrm.activitystreams.populate_stream_task.delay") as mock:
            activitystreams.populate_streams_on_account_create_command(
                self.local_user.id
            )
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], "books")
        self.assertEqual(args[1], self.local_user.id)

    def test_remove_statuses_on_block(self):
        """don't show statuses from blocked users"""
        with patch("bookwyrm.activitystreams.remove_user_statuses_task.delay") as mock:
            models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    def test_add_statuses_on_unblock(self):
        """re-add statuses on unblock"""
        block = models.UserBlocks.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )

        with patch("bookwyrm.activitystreams.add_user_statuses_task.delay") as mock:
            block.delete()

        args = mock.call_args[0]
        kwargs = mock.call_args.kwargs
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)
        self.assertEqual(kwargs["stream_list"], ["local", "books"])

    def test_add_statuses_on_unblock_reciprocal_block(self):
        """re-add statuses on unblock"""
        block = models.UserBlocks.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        block = models.UserBlocks.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
        )

        with patch("bookwyrm.activitystreams.add_user_statuses_task.delay") as mock:
            block.delete()

        self.assertEqual(mock.call_count, 0)
