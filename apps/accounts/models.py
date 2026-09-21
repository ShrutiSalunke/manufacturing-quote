from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        QUOTER = "QUOTER", "Quoter"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.QUOTER)

    @property
    def is_app_admin(self):
        if self.is_superuser or self.role == self.Role.ADMIN:
            return True
        try:
            from apps.core.permissions import feature_rbac_enabled, user_can

            if not feature_rbac_enabled():
                return False
            return user_can(self, "access_control", "view")
        except Exception:
            return False

    def __str__(self):
        return self.email or self.username
