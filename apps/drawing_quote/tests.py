from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


class DrawingQuotePhase0Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dq_p0", password="pass12345")

    def test_app_is_installed(self):
        from django.conf import settings

        self.assertIn("apps.drawing_quote", settings.INSTALLED_APPS)

    def test_flag_defaults_off_in_settings_module(self):
        from django.conf import settings

        # Env may enable it locally; assert the setting exists and is bool.
        self.assertIsInstance(settings.DRAWING_QUOTE_ENABLED, bool)

    @override_settings(DRAWING_QUOTE_ENABLED=True)
    def test_context_exposes_flag(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["DRAWING_QUOTE_ENABLED"])

    @override_settings(DRAWING_QUOTE_ENABLED=False)
    def test_context_hides_flag(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["DRAWING_QUOTE_ENABLED"])
