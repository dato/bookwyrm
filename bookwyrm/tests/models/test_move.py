""" testing move models """
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from bookwyrm import models


class MoveUser(TestCase):
    """move your account to another identity"""

    @classmethod
    def setUpTestData(cls):
        """we need some users for this"""
        cls.target_user = models.User.objects.create_user(
            "rat",
            "rat@rat.com",
            "ratword",
            local=False,
            remote_id="https://example.com/users/rat",
            inbox="https://example.com/users/rat/inbox",
            outbox="https://example.com/users/rat/outbox",
        )
        cls.origin_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
        )
        cls.origin_user.remote_id = "http://local.com/user/mouse"
        cls.origin_user.save(broadcast=False, update_fields=["remote_id"])

    def test_user_move_unauthorized(self):
        """attempt a user move without alsoKnownAs set"""

        with self.assertRaises(PermissionDenied):
            models.MoveUser.objects.create(
                user=self.origin_user,
                object=self.origin_user.remote_id,
                target=self.target_user,
            )

    def test_user_move(self):
        """move user"""

        self.target_user.also_known_as.add(self.origin_user.id)
        self.target_user.save(broadcast=False)

        models.MoveUser.objects.create(
            user=self.origin_user,
            object=self.origin_user.remote_id,
            target=self.target_user,
        )
        self.assertEqual(self.origin_user.moved_to, self.target_user.remote_id)
