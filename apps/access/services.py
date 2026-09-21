"""Seed permissions, system roles, and map legacy User.role → UserRole."""
from __future__ import annotations

from django.contrib.auth import get_user_model

from .catalog import MATRIX_ACTIONS, MODULES, all_permission_defs
from .engine import clear_user_perm_cache
from .models import Permission, Role, RolePermission, UserRole


# Role code → set of "module.action" or "*" for all
ROLE_SEEDS = (
    {
        "code": "super_admin",
        "name": "Super Admin",
        "description": "Full system access including Access Control.",
        "level": 1,
        "grants": "*",
    },
    {
        "code": "plant_admin",
        "name": "Plant Admin",
        "description": "Catalog, processes, and quote operations. No Access Control.",
        "level": 2,
        "grants": "all_except_access",
    },
    {
        "code": "quoter",
        "name": "Quoter",
        "description": "Create and manage quotes; view catalog.",
        "level": 3,
        "grants": "quoter",
    },
    {
        "code": "viewer",
        "name": "Viewer",
        "description": "Read-only access to quoting surfaces.",
        "level": 4,
        "grants": "viewer",
    },
)


def _quoter_codenames() -> set[str]:
    codes = {
        "dashboard.view",
        "quotes.view",
        "quotes.create",
        "quotes.edit",
        "quotes.calculate",
        "quotes.issue",
        "quotes.clone",
        "quotes.preview_pdf",
        "clients.view",
        "clients.create",
        "clients.edit",
    }
    for mod in ("materials", "machines", "labor", "processes", "subprocesses"):
        codes.add(f"{mod}.view")
    return codes


def _viewer_codenames() -> set[str]:
    return {
        "dashboard.view",
        "quotes.view",
        "clients.view",
        "materials.view",
        "machines.view",
        "labor.view",
        "processes.view",
        "subprocesses.view",
    }


def _plant_admin_codenames(all_codes: set[str]) -> set[str]:
    return {c for c in all_codes if not c.startswith("access_control.")}


def ensure_permissions() -> int:
    created = 0
    for module, action, label in all_permission_defs():
        _, was_created = Permission.objects.update_or_create(
            module=module,
            action=action,
            defaults={"label": label},
        )
        if was_created:
            created += 1
    return created


def ensure_roles() -> dict[str, Role]:
    ensure_permissions()
    all_codes = {f"{p.module}.{p.action}" for p in Permission.objects.all()}
    perm_by_code = {
        f"{p.module}.{p.action}": p for p in Permission.objects.all()
    }
    roles: dict[str, Role] = {}
    for spec in ROLE_SEEDS:
        role, _ = Role.objects.update_or_create(
            code=spec["code"],
            defaults={
                "name": spec["name"],
                "description": spec["description"],
                "level": spec["level"],
                "is_system": True,
                "is_active": True,
            },
        )
        roles[spec["code"]] = role
        grant = spec["grants"]
        if grant == "*":
            wanted = all_codes
        elif grant == "all_except_access":
            wanted = _plant_admin_codenames(all_codes)
        elif grant == "quoter":
            wanted = _quoter_codenames()
        elif grant == "viewer":
            wanted = _viewer_codenames()
        else:
            wanted = set()

        RolePermission.objects.filter(role=role).exclude(
            permission__in=[perm_by_code[c] for c in wanted if c in perm_by_code]
        ).delete()
        for code in wanted:
            perm = perm_by_code.get(code)
            if perm:
                RolePermission.objects.get_or_create(role=role, permission=perm)
    return roles


def sync_legacy_user_roles() -> int:
    """Assign UserRole from User.role when the user has no access roles yet."""
    User = get_user_model()
    roles = ensure_roles()
    assigned = 0
    for user in User.objects.all().iterator():
        if UserRole.objects.filter(user=user).exists():
            continue
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            role = roles["super_admin"]
        else:
            role = roles["quoter"]
        UserRole.objects.create(user=user, role=role)
        clear_user_perm_cache(user.pk)
        assigned += 1
    return assigned


def seed_access_control() -> dict:
    perm_created = ensure_permissions()
    ensure_roles()
    users_mapped = sync_legacy_user_roles()
    return {
        "permissions_created": perm_created,
        "roles": list(Role.objects.values_list("code", flat=True)),
        "users_mapped": users_mapped,
        "modules": [m[0] for m in MODULES],
        "matrix_actions": list(MATRIX_ACTIONS),
    }
