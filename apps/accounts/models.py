from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


def feature_rbac_enabled() -> bool:
    """Soft flag — False on Main; True when Access Control is merged and enabled."""
    return bool(getattr(settings, "FEATURE_RBAC", False))


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        QUOTER = "QUOTER", "Quoter"

    # Kept for merge-safety with feature/rbac. Main UI no longer offers Quoter vs Admin;
    # new users are always stored as ADMIN (full access).
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.ADMIN
    )

    @property
    def is_app_admin(self):
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        if feature_rbac_enabled():
            try:
                from apps.access.engine import has_perm

                return has_perm(self, "access_control", "view") or self.role == self.Role.ADMIN
            except Exception:
                return self.role == self.Role.ADMIN
        # Main / small client: every active user has full access (no Quoter split).
        return True

    def __str__(self):
        return self.email or self.username
