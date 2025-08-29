""" test populating user streams """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models
from bookwyrm.management.commands.populate_streams import populate_streams


class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """we need some stuff"""
        cls.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        cls.another_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
        )
        models.User.objects.create_user(
            "gerbil",
            "gerbil@gerbil.gerbil",
            "password",
            local=True,
            localname="gerbil",
            is_active=False,
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
        cls.book = models.Edition.objects.create(title="test book")

    def test_populate_streams(self):
        """make sure the function on the redis manager gets called"""
        models.Comment.objects.create(
            user=self.local_user, content="hi", book=self.book
        )
        with (
            patch("bookwyrm.activitystreams.populate_stream_task.delay") as redis_mock,
            patch("bookwyrm.lists_stream.populate_lists_task.delay") as list_mock,
        ):
            populate_streams()
        self.assertEqual(redis_mock.call_count, 6)  # 2 users x 3 streams
        self.assertEqual(list_mock.call_count, 2)  # 2 users
