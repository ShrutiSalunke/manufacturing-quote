from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .catalog import MATRIX_ACTIONS, MODULES
from .decorators import access_admin_required, rbac_feature_required
from .engine import clear_user_perm_cache, feature_rbac_enabled
from .models import Permission, Role, RolePermission, UserRole

_MATRIX_ACTION_LABELS = (
    ("view", "View"),
    ("create", "Create"),
    ("edit", "Edit"),
    ("soft_delete", "Soft delete"),
    ("permanent_delete", "Permanent delete"),
    ("admin", "Admin"),
)


def _hub_context(selected_role_id: int | None = None):
    """Fast hub payload — no seeding; minimal round-trips to the remote DB."""
    User = get_user_model()
    roles = list(
        Role.objects.filter(is_active=True)
        .annotate(user_count=Count("user_links", distinct=True))
        .order_by("level", "name")
        .only("id", "code", "name", "description", "level", "is_active")
    )

    selected_role = None
    if selected_role_id:
        selected_role = next((r for r in roles if r.pk == selected_role_id), None)
        if selected_role is None:
            selected_role = get_object_or_404(Role, pk=selected_role_id, is_active=True)
            selected_role.user_count = UserRole.objects.filter(role=selected_role).count()
    elif roles:
        selected_role = roles[0]

    granted = set()
    members = []
    if selected_role:
        granted = set(
            RolePermission.objects.filter(role_id=selected_role.pk).values_list(
                "permission__module", "permission__action"
            )
        )
        members = list(
            UserRole.objects.filter(role_id=selected_role.pk)
            .select_related("user")
            .only(
                "id",
                "role_id",
                "user_id",
                "user__id",
                "user__email",
                "user__username",
                "user__first_name",
                "user__last_name",
            )
            .order_by("user__email", "user__username")[:12]
        )

    matrix_rows = [
        {
            "module": module,
            "label": label,
            "cells": [
                {"action": action, "granted": (module, action) in granted}
                for action in MATRIX_ACTIONS
            ],
        }
        for module, label in MODULES
    ]

    member_ids = {m.user_id for m in members}
    # Small assign list: active users not already shown as members (cap 40).
    assignable_users = list(
        User.objects.filter(is_active=True)
        .exclude(pk__in=member_ids)
        .order_by("email", "username")
        .only("id", "email", "username")[:40]
    )

    role_count = len(roles)
    # Prefer annotated totals when possible; one cheap count for users + grants.
    user_count = User.objects.filter(is_active=True).count()
    grants_total = RolePermission.objects.count() if role_count else 0

    return {
        "page_title": "Access Control",
        "feature_rbac": feature_rbac_enabled(),
        "roles": roles,
        "selected_role": selected_role,
        "matrix_actions": _MATRIX_ACTION_LABELS,
        "matrix_rows": matrix_rows,
        "members": members,
        "stats": {
            "roles": role_count,
            "users": user_count,
            "modules": len(MODULES),
            "grants": grants_total,
        },
        "assignable_users": assignable_users,
    }


@rbac_feature_required
@access_admin_required
def access_hub(request):
    role_id = request.GET.get("role")
    selected_id = int(role_id) if role_id and str(role_id).isdigit() else None
    return render(request, "access/hub.html", _hub_context(selected_id))


@rbac_feature_required
@access_admin_required
@require_POST
def role_save_permissions(request, role_pk):
    role = get_object_or_404(Role, pk=role_pk, is_active=True)

    wanted: list[tuple[str, str]] = []
    for module, _ in MODULES:
        for action in MATRIX_ACTIONS:
            if request.POST.get(f"perm__{module}__{action}"):
                wanted.append((module, action))

    perm_map = {
        (p.module, p.action): p.pk
        for p in Permission.objects.filter(
            module__in=[m for m, _ in MODULES],
            action__in=list(MATRIX_ACTIONS),
        ).only("id", "module", "action")
    }

    RolePermission.objects.filter(role=role).delete()
    if wanted:
        RolePermission.objects.bulk_create(
            [
                RolePermission(role_id=role.pk, permission_id=perm_map[(m, a)])
                for m, a in wanted
                if (m, a) in perm_map
            ],
            ignore_conflicts=True,
        )

    for user_id in UserRole.objects.filter(role=role).values_list("user_id", flat=True):
        clear_user_perm_cache(user_id)
    messages.success(request, f"Permissions updated for {role.name}.")
    return redirect(f"{reverse('access:hub')}?role={role.pk}")


@rbac_feature_required
@access_admin_required
@require_POST
def role_assign_user(request, role_pk):
    role = get_object_or_404(Role, pk=role_pk, is_active=True)
    User = get_user_model()
    user_id = request.POST.get("user_id")
    user = get_object_or_404(User, pk=user_id, is_active=True)
    _, created = UserRole.objects.get_or_create(user=user, role=role)
    clear_user_perm_cache(user.pk)
    if created:
        messages.success(request, f"Assigned {user} to {role.name}.")
    else:
        messages.info(request, f"{user} already has {role.name}.")
    return redirect(f"{reverse('access:hub')}?role={role.pk}")


@rbac_feature_required
@access_admin_required
@require_POST
def role_remove_user(request, role_pk, user_pk):
    role = get_object_or_404(Role, pk=role_pk, is_active=True)
    deleted, _ = UserRole.objects.filter(role=role, user_id=user_pk).delete()
    clear_user_perm_cache(user_pk)
    if deleted:
        messages.success(request, "User removed from role.")
    return redirect(f"{reverse('access:hub')}?role={role.pk}")
