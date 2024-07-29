""" testing lists_stream """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import lists_stream, models


class ListsStreamSignals(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """database setup"""
        cls.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        cls.another_user = models.User.objects.create_user(
            "fish", "fish@fish.fish", "password", local=True, localname="fish"
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

    def test_add_list_on_create_command(self):
        """a new lists has entered"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        with patch("bookwyrm.lists_stream.add_list_task.delay") as mock:
            lists_stream.add_list_on_create_command(book_list.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], book_list.id)

    def test_remove_list_on_delete(self):
        """delete a list"""
        book_list = models.List.objects.create(
            user=self.remote_user, name="hi", privacy="public"
        )
        with patch("bookwyrm.lists_stream.remove_list_task.delay") as mock:
            lists_stream.remove_list_on_delete(models.List, book_list)
        args = mock.call_args[0]
        self.assertEqual(args[0], book_list.id)

    def test_populate_lists_on_account_create_command(self):
        """create streams for a user"""
        with patch("bookwyrm.lists_stream.populate_lists_task.delay") as mock:
            lists_stream.add_list_on_account_create_command(self.local_user.id)
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)

    def test_remove_lists_on_block(self):
        """don't show lists from blocked users"""
        with patch("bookwyrm.lists_stream.remove_user_lists_task.delay") as mock:
            models.UserBlocks.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
            )

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    def test_add_lists_on_unblock(self):
        """re-add lists on unblock"""
        block = models.UserBlocks.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        with patch("bookwyrm.lists_stream.add_user_lists_task.delay") as mock:
            block.delete()

        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user.id)
        self.assertEqual(args[1], self.remote_user.id)

    def test_add_lists_on_unblock_reciprocal_block(self):
        """dont' re-add lists on unblock if there's a block the other way"""
        block = models.UserBlocks.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        block = models.UserBlocks.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
        )
        with patch("bookwyrm.lists_stream.add_user_lists_task.delay") as mock:
            block.delete()

        self.assertFalse(mock.called)
