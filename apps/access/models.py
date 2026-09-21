from django.conf import settings
from django.db import models


class Role(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    level = models.PositiveSmallIntegerField(
        default=99,
        help_text="Lower number = higher privilege (L1=1). Used for UI ordering only.",
    )
    is_system = models.BooleanField(
        default=False,
        help_text="Seeded roles; code cannot be deleted from UI.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level", "name"]

    def __str__(self):
        return self.name


class Permission(models.Model):
    module = models.SlugField(max_length=50)
    action = models.SlugField(max_length=50)
    label = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["module", "action"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "action"],
                name="access_perm_module_action_uniq",
            ),
        ]

    def __str__(self):
        return self.label or f"{self.module}.{self.action}"

    @property
    def codename(self):
        return f"{self.module}.{self.action}"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="access_roleperm_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.role.code} → {self.permission}"


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_roles",
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                name="access_userrole_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.role.code}"


class OverrideEffect(models.TextChoices):
    ALLOW = "ALLOW", "Allow"
    DENY = "DENY", "Deny"


class UserPermissionOverride(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_overrides",
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="user_overrides"
    )
    effect = models.CharField(
        max_length=10, choices=OverrideEffect.choices, default=OverrideEffect.ALLOW
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "permission"],
                name="access_useroverride_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.user} {self.effect} {self.permission}"
