""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class BlockViews(TestCase):
    """view user and edit profile"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
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
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_block_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Block.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_block_post(self):
        """create a "block" database entry from an activity"""
        view = views.Block.as_view()
        self.local_user.followers.add(self.remote_user)
        models.UserFollowRequest.objects.create(
            user_subject=self.local_user, user_object=self.remote_user
        )
        self.assertTrue(models.UserFollows.objects.exists())
        self.assertTrue(models.UserFollowRequest.objects.exists())

        request = self.factory.post("")
        request.user = self.local_user

        view(request, self.remote_user.id)

        block = models.UserBlocks.objects.get()
        self.assertEqual(block.user_subject, self.local_user)
        self.assertEqual(block.user_object, self.remote_user)

        self.assertFalse(models.UserFollows.objects.exists())
        self.assertFalse(models.UserFollowRequest.objects.exists())

    def test_unblock(self):
        """undo a block"""
        self.local_user.blocks.add(self.remote_user)
        request = self.factory.post("")
        request.user = self.local_user

        views.unblock(request, self.remote_user.id)
        self.assertFalse(models.UserBlocks.objects.exists())
