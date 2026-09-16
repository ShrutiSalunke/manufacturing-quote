from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        QUOTER = "QUOTER", "Quoter"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.QUOTER)

    @property
    def is_app_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return self.email or self.username
