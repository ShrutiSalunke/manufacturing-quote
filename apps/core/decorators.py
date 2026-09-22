from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            # Main (FEATURE_RBAC off): is_app_admin is True for every active user.
            if "ADMIN" in roles and getattr(user, "is_app_admin", False):
                return view_func(request, *args, **kwargs)
            if getattr(user, "role", None) in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")

        return _wrapped

    return decorator


def admin_required(view_func):
    """Gate for admin-only views. Uses User.is_app_admin (full access on Main)."""
    return role_required("ADMIN")(view_func)
