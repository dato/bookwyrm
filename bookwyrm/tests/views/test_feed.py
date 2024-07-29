""" test for app action functionality """
from unittest.mock import patch
import pathlib

from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.validate_html import validate_html


class FeedViews(TestCase):
    """activity feed, statuses, dms"""

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
        cls.another_user = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
        )
        cls.book = models.Edition.objects.create(
            parent_work=models.Work.objects.create(title="hi"),
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    @patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
    def test_feed(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Feed.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "home")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    @patch("bookwyrm.activitystreams.ActivityStream.get_activity_stream")
    def test_save_feed_settings(self, *_):
        """update display preferences"""
        self.assertEqual(
            self.local_user.feed_status_types,
            ["review", "comment", "quotation", "everything"],
        )
        view = views.Feed.as_view()
        form = forms.FeedStatusTypesForm(instance=self.local_user)
        form.data["feed_status_types"] = "review"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request, "home")

        self.assertEqual(result.status_code, 200)
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.feed_status_types, ["review"])

    def test_status_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()
        status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_status_page_not_found(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "mouse", 12345)

    def test_status_page_not_found_wrong_user(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()
        another_user = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.rat",
            "password",
            local=True,
            localname="rat",
        )
        status = models.Status.objects.create(content="hi", user=another_user)

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "mouse", status.id)

    def test_status_page_with_image(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Status.as_view()

        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        status = models.Review.objects.create(
            content="hi",
            user=self.local_user,
            book=self.book,
        )
        attachment = models.Image.objects.create(status=status, caption="alt text here")
        with open(image_path, "rb") as image_file:
            attachment.image.save("test.jpg", image_file)

        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_replies_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Replies.as_view()
        status = models.Status.objects.create(content="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.feed.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", status.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_direct_messages_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DirectMessage.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_direct_messages_page_user(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DirectMessage.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "nutria")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context_data["partner"], self.another_user)

    def test_get_suggested_book(self):
        """gets books the ~*~ algorithm ~*~ thinks you want to post about"""
        models.ShelfBook.objects.create(
            book=self.book,
            user=self.local_user,
            shelf=self.local_user.shelf_set.get(identifier="reading"),
        )
        suggestions = views.feed.get_suggested_books(self.local_user)
        self.assertEqual(suggestions[0]["name"], "Currently Reading")
        self.assertEqual(suggestions[0]["books"][0], self.book)
