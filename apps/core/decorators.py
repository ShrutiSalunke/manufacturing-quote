from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or getattr(user, "role", None) in roles:
                return view_func(request, *args, **kwargs)
            if "ADMIN" in roles and getattr(user, "is_app_admin", False):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")

        return _wrapped

    return decorator


def admin_required(view_func):
    return role_required("ADMIN")(view_func)
