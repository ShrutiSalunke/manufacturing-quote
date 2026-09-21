"""
Effective permission resolution.

When FEATURE_RBAC is off, falls back to legacy User.role (ADMIN / QUOTER).
When on, uses role grants ∪ ALLOW overrides − DENY overrides.
Superusers always pass.

Results are memoized on the user instance for the request, and in Django cache.
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

from .catalog import MODULES

_ATTR_BUNDLE = "_mq_access_bundle"


def feature_rbac_enabled() -> bool:
    return bool(getattr(settings, "FEATURE_RBAC", False))


def _legacy_is_admin(user) -> bool:
    """Legacy admin check — must NOT call user.is_app_admin (avoids recursion)."""
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == "ADMIN"
    )


def _legacy_has_perm(user, module: str, action: str) -> bool:
    """ADMIN / QUOTER behavior used when RBAC feature is off or unseeded."""
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
    if action in ("soft_delete",) and module in (
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
    if role == "QUOTER" or not is_admin:
        if module in ("imports",) and action != "view":
            return False
        if action in ("view", "create", "edit") and module in (
            "quotes",
            "clients",
        ):
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


def _cache_key(user_id: int) -> str:
    return f"access:perms:v1:{user_id}"


def clear_user_perm_cache(user_id: int | None = None) -> None:
    if user_id is None:
        return
    cache.delete(_cache_key(user_id))


def _load_rbac_perm_set(user) -> set[str] | None:
    """
    Load effective RBAC permission set.
    Returns None if the user has no UserRole rows (use legacy fallback).
    """
    from .models import OverrideEffect, RolePermission, UserPermissionOverride, UserRole

    role_ids = list(
        UserRole.objects.filter(user_id=user.pk, role__is_active=True).values_list(
            "role_id", flat=True
        )
    )
    if not role_ids:
        return None

    allowed: set[str] = set(
        f"{module}.{action}"
        for module, action in RolePermission.objects.filter(
            role_id__in=role_ids
        ).values_list("permission__module", "permission__action")
    )

    for module, action, effect in UserPermissionOverride.objects.filter(
        user_id=user.pk
    ).values_list("permission__module", "permission__action", "effect"):
        key = f"{module}.{action}"
        if effect == OverrideEffect.ALLOW:
            allowed.add(key)
        elif effect == OverrideEffect.DENY:
            allowed.discard(key)
    return allowed


def _resolve_bundle(user) -> dict:
    """
    Bundle:
      mode = "all" | "legacy" | "rbac"
      perms = set[str] when mode == "rbac"
    """
    if getattr(user, "is_superuser", False):
        return {"mode": "all", "perms": None}
    if not feature_rbac_enabled():
        return {"mode": "legacy", "perms": None}

    cached = cache.get(_cache_key(user.pk))
    if cached is not None:
        # cached may be the string "legacy" or a list/set of perms
        if cached == "__legacy__":
            return {"mode": "legacy", "perms": None}
        return {"mode": "rbac", "perms": set(cached)}

    loaded = _load_rbac_perm_set(user)
    if loaded is None:
        cache.set(_cache_key(user.pk), "__legacy__", timeout=300)
        return {"mode": "legacy", "perms": None}

    cache.set(_cache_key(user.pk), list(loaded), timeout=300)
    return {"mode": "rbac", "perms": loaded}


def user_perm_bundle(user) -> dict:
    if not getattr(user, "is_authenticated", False):
        return {"mode": "legacy", "perms": set()}
    bundle = getattr(user, _ATTR_BUNDLE, None)
    if bundle is not None:
        return bundle
    bundle = _resolve_bundle(user)
    setattr(user, _ATTR_BUNDLE, bundle)
    return bundle


def user_perm_set(user) -> set[str] | None:
    """
    Return effective permission codenames when RBAC applies.
    None means use legacy fallback (or superuser handled in has_perm).
    """
    bundle = user_perm_bundle(user)
    if bundle["mode"] == "all":
        return None
    if bundle["mode"] == "legacy":
        return None
    return bundle["perms"]


def has_perm(user, module: str, action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False

    bundle = user_perm_bundle(user)
    if bundle["mode"] == "all":
        return True
    if bundle["mode"] == "legacy":
        return _legacy_has_perm(user, module, action)
    return f"{module}.{action}" in (bundle["perms"] or set())


def module_labels() -> list[tuple[str, str]]:
    return list(MODULES)
