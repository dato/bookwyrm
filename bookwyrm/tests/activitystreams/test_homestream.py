""" testing activitystreams """
from django.test import TestCase
from bookwyrm import activitystreams, models


class Activitystreams(TestCase):
    """using redis to build activity streams"""

    @classmethod
    def setUpTestData(cls):
        """use a test csv"""
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

    def test_homestream_get_audience(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.HomeStream().get_audience(status)
        self.assertEqual(users, [])

    def test_homestream_get_audience_with_mentions(self):
        """get a list of users that should see a status"""
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        status.mention_users.add(self.local_user)
        users = activitystreams.HomeStream().get_audience(status)
        self.assertFalse(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)

    def test_homestream_get_audience_with_relationship(self):
        """get a list of users that should see a status"""
        self.remote_user.followers.add(self.local_user)
        status = models.Status.objects.create(
            user=self.remote_user, content="hi", privacy="public"
        )
        users = activitystreams.HomeStream().get_audience(status)
        self.assertTrue(self.local_user.id in users)
        self.assertFalse(self.another_user.id in users)
