from django.conf import settings


def app_context(request):
    return {
        "COMPANY_NAME": getattr(settings, "COMPANY_NAME", "Manufacturing Quote"),
        "correlation_id": getattr(request, "correlation_id", None),
        "FEATURE_RBAC": bool(getattr(settings, "FEATURE_RBAC", False)),
    }
