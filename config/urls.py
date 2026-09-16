from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("templates/", include("apps.templates_engine.urls")),
    path("quotes/", include("apps.quotes.urls")),
    path("imports/", include("apps.imports_excel.urls")),
    path("error-logs/", include("apps.auditlog.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
]

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
