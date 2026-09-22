from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class UserModelAccessTests(TestCase):
    def test_active_user_is_app_admin_when_rbac_off(self):
        u = User.objects.create_user(
            username="anyone",
            email="anyone@example.com",
            password="TestPass123!",
            role=User.Role.QUOTER,
        )
        self.assertTrue(u.is_app_admin)

    def test_inactive_user_not_app_admin(self):
        u = User.objects.create_user(
            username="gone",
            email="gone@example.com",
            password="TestPass123!",
            is_active=False,
        )
        self.assertFalse(u.is_app_admin)


class UsersCrudTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )
        self.client.login(username="admin", password="Admin123!")

    def test_list_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_list_ok(self):
        resp = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Users")
        self.assertContains(resp, "admin@example.com")

    def test_create_user_full_access_and_redirect_list(self):
        resp = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(resp, reverse("accounts:user_list"))
        created = User.objects.get(username="newuser")
        self.assertEqual(created.email, "new@example.com")
        self.assertEqual(created.role, User.Role.ADMIN)
        self.assertTrue(created.check_password("StrongPass123!"))
        self.assertTrue(created.is_app_admin)

    def test_create_password_mismatch(self):
        resp = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "bad",
                "email": "bad@example.com",
                "password1": "StrongPass123!",
                "password2": "DifferentPass123!",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="bad").exists())

    def test_create_duplicate_email(self):
        resp = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "other",
                "email": "ADMIN@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="admin@example.com").count(), 1)

    def test_edit_user(self):
        other = User.objects.create_user(
            username="editme",
            email="edit@example.com",
            password="OldPass123!",
        )
        resp = self.client.post(
            reverse("accounts:user_edit", args=[other.pk]),
            {
                "username": "editme",
                "email": "edited@example.com",
                "first_name": "Ed",
                "last_name": "Ited",
                "is_active": "on",
                "password1": "",
                "password2": "",
            },
        )
        self.assertRedirects(resp, reverse("accounts:user_list"))
        other.refresh_from_db()
        self.assertEqual(other.email, "edited@example.com")
        self.assertTrue(other.check_password("OldPass123!"))

    def test_cannot_deactivate_self_via_post(self):
        resp = self.client.post(reverse("accounts:user_deactivate", args=[self.admin.pk]))
        self.assertRedirects(resp, reverse("accounts:user_list"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_deactivate_and_activate(self):
        other = User.objects.create_user(
            username="temp",
            email="temp@example.com",
            password="TempPass123!",
        )
        resp = self.client.post(reverse("accounts:user_deactivate", args=[other.pk]))
        self.assertRedirects(resp, reverse("accounts:user_list"))
        other.refresh_from_db()
        self.assertFalse(other.is_active)

        resp = self.client.post(reverse("accounts:user_activate", args=[other.pk]))
        self.assertRedirects(resp, reverse("accounts:user_list"))
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        self.assertEqual(other.role, User.Role.ADMIN)

    def test_search_filter(self):
        User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="AlicePass123!",
        )
        resp = self.client.get(reverse("accounts:user_list"), {"q": "alice"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "alice@example.com")
        self.assertEqual(len(resp.context["users"]), 1)
        self.assertEqual(resp.context["users"][0].username, "alice")

    @override_settings(FEATURE_RBAC=True)
    def test_create_redirect_falls_back_when_access_missing(self):
        """FEATURE_RBAC on but no access:hub → still lands on user list."""
        resp = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "rbacuser",
                "email": "rbac@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(resp, reverse("accounts:user_list"))
