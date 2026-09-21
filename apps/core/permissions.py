"""
Merge-safe permission checks.

- With FEATURE_RBAC + apps.access: uses the RBAC engine.
- Otherwise: legacy ADMIN / QUOTER rules (same behavior as Main without Access Control).

Templates and views should call `user_can` / `require_perm` so cherry-picking or
disabling FEATURE_RBAC never hard-depends on Access Control UI working.
"""
from __future__ import annotations


def feature_rbac_enabled() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "FEATURE_RBAC", False))
    except Exception:
        return False


def _legacy_is_admin(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == "ADMIN"
    )


def legacy_user_can(user, module: str, action: str) -> bool:
    """Pre-RBAC behavior — safe when apps.access is absent."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    role = getattr(user, "role", None)
    is_admin = _legacy_is_admin(user)

    if module == "access_control":
        return is_admin
    if module == "error_logs":
        return is_admin
    if module == "custom_fields" and action != "view":
        return is_admin
    if action == "permanent_delete":
        return is_admin
    if action == "soft_delete" and module in (
        "materials",
        "machines",
        "labor",
        "processes",
        "subprocesses",
        "clients",
        "custom_fields",
    ):
        return is_admin
    if action == "admin":
        return is_admin
    if module == "dashboard" and action == "view":
        return True
    if module == "onboarding":
        return True
    if role == "QUOTER" or not is_admin:
        if module == "imports" and action not in ("view", "upload", "download_template"):
            return action == "view"
        if module == "imports" and action in ("view", "upload", "download_template"):
            return True
        if action in ("view", "create", "edit") and module in ("quotes", "clients"):
            return True
        if action == "view" and module in (
            "materials",
            "machines",
            "labor",
            "processes",
            "subprocesses",
            "imports",
        ):
            return True
        if module == "quotes" and action in (
            "calculate",
            "issue",
            "clone",
            "preview_pdf",
        ):
            return True
        return False
    return True


def user_can(user, module: str, action: str = "view") -> bool:
    if feature_rbac_enabled():
        try:
            from apps.access.engine import has_perm

            return has_perm(user, module, action)
        except Exception:
            return legacy_user_can(user, module, action)
    return legacy_user_can(user, module, action)
