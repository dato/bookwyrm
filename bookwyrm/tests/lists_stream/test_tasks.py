""" testing lists_stream """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import lists_stream, models


class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """database setup"""
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
        cls.remote_user = models.User.objects.create_user(
            "rat",
            "rat@rat.com",
            "ratword",
            local=False,
            remote_id="https://example.com/users/rat",
            inbox="https://example.com/users/rat/inbox",
            outbox="https://example.com/users/rat/outbox",
        )
        cls.list = models.List.objects.create(
            user=cls.local_user, name="hi", privacy="public"
        )

    def test_populate_lists_task(self):
        """populate lists cache"""
        with patch("bookwyrm.lists_stream.ListsStream.populate_lists") as mock:
            lists_stream.populate_lists_task(self.local_user.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)

        with patch("bookwyrm.lists_stream.ListsStream.populate_lists") as mock:
            lists_stream.populate_lists_task(self.local_user.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)

    def test_remove_list_task(self):
        """remove a list from all streams"""
        with patch(
            "bookwyrm.lists_stream.ListsStream.remove_object_from_stores"
        ) as mock:
            lists_stream.remove_list_task(self.list.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.list.id)

    def test_add_list_task(self):
        """add a list to all streams"""
        with patch("bookwyrm.lists_stream.ListsStream.add_list") as mock:
            lists_stream.add_list_task(self.list.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.list)

    def test_remove_user_lists_task(self):
        """remove all lists by a user from another users' feeds"""
        with patch("bookwyrm.lists_stream.ListsStream.remove_user_lists") as mock:
            lists_stream.remove_user_lists_task(
                self.local_user.id, self.another_user.id
            )
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

        with patch("bookwyrm.lists_stream.ListsStream.remove_user_lists") as mock:
            lists_stream.remove_user_lists_task(
                self.local_user.id, self.another_user.id
            )
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

    def test_add_user_lists_task(self):
        """add a user's lists to another users feeds"""
        with patch("bookwyrm.lists_stream.ListsStream.add_user_lists") as mock:
            lists_stream.add_user_lists_task(self.local_user.id, self.another_user.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

        with patch("bookwyrm.lists_stream.ListsStream.add_user_lists") as mock:
            lists_stream.add_user_lists_task(self.local_user.id, self.another_user.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)
