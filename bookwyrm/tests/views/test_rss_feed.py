""" testing import """
from django.test import RequestFactory, TestCase

from bookwyrm import models
from bookwyrm.views import rss_feed


class RssFeedView(TestCase):
    """rss feed behaves as expected"""

    @classmethod
    def setUpTestData(cls):
        cls.local_user = models.User.objects.create_user(
            "rss_user", "rss@test.rss", "password", local=True
        )
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_rss_empty(self):
        """load an rss feed"""
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Status updates from rss_user", result.content)

    def test_rss_comment(self):
        """load an rss feed"""
        models.Comment.objects.create(
            content="comment test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Example Edition", result.content)

    def test_rss_review(self):
        """load an rss feed"""
        models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3,
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

    def test_rss_quotation(self):
        """load an rss feed"""
        models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

        self.assertIn(b"a sickening sense", result.content)

    def test_rss_comment_only(self):
        """load an rss feed"""
        models.Comment.objects.create(
            content="comment test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssCommentsOnlyFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Example Edition", result.content)

    def test_rss_review_only(self):
        """load an rss feed"""
        models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3,
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssReviewsOnlyFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

    def test_rss_quotation_only(self):
        """load an rss feed"""
        models.Quotation.objects.create(
            quote="a sickening sense",
            content="test content",
            user=self.local_user,
            book=self.book,
        )
        view = rss_feed.RssQuotesOnlyFeed()
        request = self.factory.get("/user/rss_user/rss")
        request.user = self.local_user
        result = view(request, username=self.local_user.username)
        self.assertEqual(result.status_code, 200)

        self.assertIn(b"a sickening sense", result.content)

    def test_rss_shelf(self, *_):
        """load the rss feed of a shelf"""
        # make the shelf
        shelf = models.Shelf.objects.create(
            name="Test Shelf", identifier="test-shelf", user=self.local_user
        )
        # put the shelf on the book
        models.ShelfBook.objects.create(
            book=self.book,
            shelf=shelf,
            user=self.local_user,
        )
        view = rss_feed.RssShelfFeed()
        request = self.factory.get("/user/books/test-shelf/rss")
        request.user = self.local_user
        result = view(
            request, username=self.local_user.username, shelf_identifier="test-shelf"
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Example Edition", result.content)
