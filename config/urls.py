from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.static import serve


def root(request):
    """Site root: login for guests, dashboard when already signed in."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return redirect("accounts:login")


urlpatterns = [
    path("", root, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("templates/", include("apps.templates_engine.urls")),  # legacy; not linked in UI
    path("processes/", include("apps.processes.urls")),
    path("quotes/", include("apps.quotes.urls")),
    path("imports/", include("apps.imports_excel.urls")),
    path("error-logs/", include("apps.auditlog.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
]

if getattr(settings, "DRAWING_QUOTE_ENABLED", False):
    urlpatterns.append(path("drawing-quote/", include("apps.drawing_quote.urls")))


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # MVP hosting (e.g. Render without object storage): serve media files explicitly.
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
