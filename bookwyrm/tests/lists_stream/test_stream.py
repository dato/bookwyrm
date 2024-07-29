""" testing activitystreams """
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from bookwyrm import lists_stream, models


class ListsStream(TestCase):
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
        cls.stream = lists_stream.ListsStream()

    def test_lists_stream_ids(self):
        """the abstract base class for stream objects"""
        self.assertEqual(
            self.stream.stream_id(self.local_user),
            f"{self.local_user.id}-lists",
        )

    def test_get_rank(self):
        """sort order for lists"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        book_list.updated_date = datetime(2020, 1, 1, 0, 0, 0)
        self.assertEqual(self.stream.get_rank(book_list), 1577836800.0)

    def test_add_user_lists(self):
        """add all of a user's lists"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        with patch(
            "bookwyrm.lists_stream.ListsStream.bulk_add_objects_to_store"
        ) as mock:
            self.stream.add_user_lists(self.local_user, self.remote_user)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0][0], book_list)
        self.assertEqual(args[1], f"{self.local_user.id}-lists")

    def test_remove_user_lists(self):
        """remove user's lists"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        with patch(
            "bookwyrm.lists_stream.ListsStream.bulk_remove_objects_from_store"
        ) as mock:
            self.stream.remove_user_lists(self.local_user, self.remote_user)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0][0], book_list)
        self.assertEqual(args[1], f"{self.local_user.id}-lists")

    def test_get_audience(self):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        users = self.stream.get_audience(book_list)
        # remote users don't have feeds
        self.assertFalse(self.remote_user in users)
        self.assertTrue(self.local_user in users)
        self.assertTrue(self.another_user in users)

    def test_get_audience_direct(self):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(users.exists())

        book_list = models.List.objects.create(
            user=self.local_user,
            name="hi",
            privacy="direct",
        )
        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
        self.assertFalse(self.remote_user in users)

    def test_get_audience_followers_remote_user(self):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="followers",
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(users.exists())

    def test_get_audience_followers_self(self):
        """get a list of users that should see a list"""
        book_list = models.List.objects.create(
            user=self.local_user,
            name="hi",
            privacy="followers",
        )
        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
        self.assertFalse(self.remote_user in users)

    def test_get_audience_followers_with_relationship(self):
        """get a list of users that should see a list"""
        self.remote_user.followers.add(self.local_user)
        book_list = models.List.objects.create(
            user=self.remote_user,
            name="hi",
            privacy="followers",
        )
        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)

    def test_get_audience_followers_with_group(self):
        """get a list of users that should see a list"""
        group = models.Group.objects.create(name="test group", user=self.remote_user)
        models.GroupMember.objects.create(
            group=group,
            user=self.local_user,
        )

        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="followers", curation="group"
        )
        users = self.stream.get_audience(book_list)
        self.assertFalse(self.local_user in users)

        book_list.group = group
        book_list.save(broadcast=False)

        users = self.stream.get_audience(book_list)
        self.assertTrue(self.local_user in users)
        self.assertFalse(self.another_user in users)
