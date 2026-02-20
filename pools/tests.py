from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


# Create your tests here.

class RulesPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret")

    def test_requires_authentication(self):
        resp = self.client.get(reverse("rules"))
        self.assertEqual(resp.status_code, 302)
        # should redirect to login
        self.assertIn(reverse("login"), resp.url)

    def test_page_renders_and_contains_heading(self):
        self.client.login(username="tester", password="secret")
        resp = self.client.get(reverse("rules"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rules")

    def test_rules_button_not_shown_on_login_join_or_rules(self):
        # Without authentication, login page should not have the link
        resp = self.client.get(reverse("login"))
        self.assertNotContains(resp, "Rules")

        # Join page requires auth, so log in first
        self.client.login(username="tester", password="secret")
        resp = self.client.get(reverse("join_pool"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Rules")

        # rules page should not show a self-referential rules button
        resp = self.client.get(reverse("rules"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "href=\"%s\"" % reverse("rules"))

    def test_nav_logout_hidden_on_rules(self):
        # the page should include exactly one logout form (in the nav) and no fixed logout
        # dashboard link should also be present in nav
        self.client.login(username="tester", password="secret")
        resp = self.client.get(reverse("rules"))
        self.assertEqual(resp.status_code, 200)
        # ensure fixed logout button is not present
        self.assertNotIn(b"auth-btn--fixed", resp.content)
        # ensure nav logout exists by checking form present
        self.assertIn(b"action=\"%s\"" % reverse("logout").encode(), resp.content)
        # only one logout form overall
        self.assertEqual(resp.content.count(b"action=\"%s\"" % reverse("logout").encode()), 1)
        # dashboard link should be rendered in nav
        self.assertIn(b"Dashboard", resp.content)
        # logout should appear before dashboard in markup
        self.assertTrue(resp.content.find(b"Logout") < resp.content.find(b"Dashboard"))
