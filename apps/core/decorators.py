from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.core.permissions import feature_rbac_enabled, user_can


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or getattr(user, "role", None) in roles:
                return view_func(request, *args, **kwargs)
            if "ADMIN" in roles and user_can(user, "access_control", "view"):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")

        return _wrapped

    return decorator


def require_perm(module: str, action: str = "view"):
    """
    Gate a view by module.action.
    Merge-safe: uses RBAC when FEATURE_RBAC is on, else legacy ADMIN/QUOTER rules.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if user_can(request.user, module, action):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied(
                f"You do not have permission for {module}.{action}."
            )

        return _wrapped

    return decorator


def admin_required(view_func):
    """
    Legacy admin gate.
    Prefer require_perm(module, action) for new code.
    When RBAC is on, equivalent to access_control.view OR error_logs.view OR legacy ADMIN.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return view_func(request, *args, **kwargs)
        if feature_rbac_enabled() and (
            user_can(user, "access_control", "view")
            or user_can(user, "error_logs", "view")
        ):
            return view_func(request, *args, **kwargs)
        if not feature_rbac_enabled() and user_can(user, "error_logs", "view"):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You do not have permission to access this page.")

    return _wrapped


def permission_required(module: str, action: str = "view"):
    """Alias used by access app / older imports."""
    return require_perm(module, action)
