""" testing models """
from django.test import TestCase

from bookwyrm import models


class Link(TestCase):
    """some activitypub oddness ahead"""

    def test_create_domain(self):
        """generated default name"""
        domain = models.LinkDomain.objects.create(domain="beep.com")
        self.assertEqual(domain.name, "beep.com")
        self.assertEqual(domain.status, "pending")

    def test_create_link_new_domain(self):
        """generates link and sets domain"""
        link = models.Link.objects.create(url="https://www.hello.com/hi-there")
        self.assertEqual(link.domain.domain, "www.hello.com")
        self.assertEqual(link.name, "www.hello.com")

    def test_create_link_existing_domain(self):
        """generate link with a known domain"""
        domain = models.LinkDomain.objects.create(domain="www.hello.com", name="Hi")

        link = models.Link.objects.create(url="https://www.hello.com/hi-there")
        self.assertEqual(link.domain, domain)
        self.assertEqual(link.name, "Hi")
