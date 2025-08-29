""" style fixes and lookups for templates """
from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import notification_page_tags


class NotificationPageTags(TestCase):
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

    def test_related_status(self):
        """gets the subclass model for a notification status"""
        status = models.Status.objects.create(content="hi", user=self.user)
        notification = models.Notification.objects.create(
            user=self.user, notification_type="MENTION", related_status=status
        )

        result = notification_page_tags.related_status(notification)
        self.assertIsInstance(result, models.Status)
