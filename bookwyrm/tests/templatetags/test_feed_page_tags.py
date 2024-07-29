""" style fixes and lookups for templates """
from django.test import TestCase

from bookwyrm import models
from bookwyrm.templatetags import feed_page_tags


class FeedPageTags(TestCase):
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
        cls.book = models.Edition.objects.create(title="Test Book")

    def test_load_subclass(self):
        """get a status' real type"""
        review = models.Review.objects.create(user=self.user, book=self.book, rating=3)
        status = models.Status.objects.get(id=review.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Review)

        quote = models.Quotation.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=quote.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Quotation)

        comment = models.Comment.objects.create(
            user=self.user, book=self.book, content="hi"
        )
        status = models.Status.objects.get(id=comment.id)
        self.assertIsInstance(status, models.Status)
        self.assertIsInstance(feed_page_tags.load_subclass(status), models.Comment)
