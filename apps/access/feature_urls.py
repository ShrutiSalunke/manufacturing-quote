"""
Access Control URL include — only mounts when FEATURE_RBAC is on.

Keeps /access/ off Main-style deploys that leave the app installed but disabled.
"""
from django.conf import settings
from django.urls import include, path

urlpatterns = []

if getattr(settings, "FEATURE_RBAC", False):
    urlpatterns = [
        path("", include("apps.access.urls")),
    ]
