""" style fixes and lookups for templates """
from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import interaction


class InteractionTags(TestCase):
    """lotta different things here"""

    @classmethod
    def setUpTestData(cls):
        """create some filler objects"""
        cls.user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.mouse",
            "mouseword",
            local=True,
            localname="mouse",
        )
        cls.remote_user = models.User.objects.create_user(
            "rat",
            "rat@rat.rat",
            "ratword",
            remote_id="http://example.com/rat",
            local=False,
        )
        cls.book = models.Edition.objects.create(title="Test Book")

    def test_get_user_liked(self):
        """did a user like a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_liked(self.user, status))
        models.Favorite.objects.create(user=self.user, status=status)
        self.assertTrue(interaction.get_user_liked(self.user, status))

    def test_get_user_boosted(self):
        """did a user boost a status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)

        self.assertFalse(interaction.get_user_boosted(self.user, status))
        models.Boost.objects.create(user=self.user, boosted_status=status)
        self.assertTrue(interaction.get_user_boosted(self.user, status))
