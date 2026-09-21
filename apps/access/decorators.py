from apps.core.permissions import feature_rbac_enabled, user_can
from apps.core.decorators import require_perm


def permission_required(module: str, action: str = "view"):
    return require_perm(module, action)


def access_admin_required(view_func):
    return require_perm("access_control", "view")(view_func)


def rbac_feature_required(view_func):
    from functools import wraps

    from django.contrib.auth.decorators import login_required
    from django.core.exceptions import PermissionDenied

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not feature_rbac_enabled():
            raise PermissionDenied("Access Control is not enabled on this deployment.")
        return view_func(request, *args, **kwargs)

    return _wrapped
