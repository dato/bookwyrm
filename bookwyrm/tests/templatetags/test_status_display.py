""" style fixes and lookups for templates """
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.templatetags import status_display


class StatusDisplayTags(TestCase):
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

    def test_get_mentions(self):
        """list of people mentioned"""
        status = models.Status.objects.create(content="hi", user=self.remote_user)
        result = status_display.get_mentions(status, self.user)
        self.assertEqual(result, "@rat@example.com ")

    def test_get_replies(self):
        """direct replies to a status"""
        parent = models.Review.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        first_child = models.Status.objects.create(
            reply_parent=parent, user=self.user, content="hi"
        )
        second_child = models.Status.objects.create(
            reply_parent=parent, user=self.user, content="hi"
        )
        third_child = models.Status.objects.create(
            reply_parent=parent,
            user=self.user,
            deleted=True,
            deleted_date=timezone.now(),
        )

        replies = status_display.get_replies(parent)
        self.assertEqual(len(replies), 2)
        self.assertTrue(first_child in replies)
        self.assertTrue(second_child in replies)
        self.assertFalse(third_child in replies)

    def test_get_parent(self):
        """get the reply parent of a status"""
        parent = models.Review.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        child = models.Status.objects.create(
            reply_parent=parent, user=self.user, content="hi"
        )
        result = status_display.get_parent(child)
        self.assertEqual(result, parent)
        self.assertIsInstance(result, models.Review)

    def test_get_boosted(self):
        """load a boosted status"""
        status = models.Review.objects.create(user=self.remote_user, book=self.book)
        boost = models.Boost.objects.create(user=self.user, boosted_status=status)
        boosted = status_display.get_boosted(boost)
        self.assertIsInstance(boosted, models.Review)
        self.assertEqual(boosted, status)

    def test_get_published_date(self):
        """date formatting"""
        date = datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now") as timezone_mock:
            timezone_mock.return_value = datetime.datetime(
                2022, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            result = status_display.get_published_date(date)
        self.assertEqual(result, "Jan. 1, 2020")

        date = datetime.datetime(2022, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now") as timezone_mock:
            timezone_mock.return_value = datetime.datetime(
                2022, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
            )
            result = status_display.get_published_date(date)
        self.assertEqual(result, "January 1")

        with patch("django.utils.timezone.now") as timezone_mock:
            timezone_mock.return_value = datetime.datetime(
                # bookwyrm-social#3365: bug with exact month deltas
                2022,
                3,
                1,
                0,
                0,
                tzinfo=datetime.timezone.utc,
            )
            result = status_display.get_published_date(date)
        self.assertEqual(result, "January 1")
