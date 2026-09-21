from django.conf import settings

from apps.core.permissions import feature_rbac_enabled, user_can


def app_context(request):
    user = getattr(request, "user", None)
    feature_rbac = feature_rbac_enabled()
    show_access = False
    if (
        feature_rbac
        and user is not None
        and getattr(user, "is_authenticated", False)
    ):
        show_access = user_can(user, "access_control", "view")
    return {
        "COMPANY_NAME": getattr(settings, "COMPANY_NAME", "Manufacturing Quote"),
        "correlation_id": getattr(request, "correlation_id", None),
        "FEATURE_RBAC": feature_rbac,
        "show_access_control": show_access,
    }
