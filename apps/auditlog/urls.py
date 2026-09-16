from django.urls import path

from . import views

app_name = "auditlog"

urlpatterns = [
    path("", views.log_list, name="log_list"),
    path("<int:pk>/", views.log_detail, name="log_detail"),
    path("purge/", views.log_purge, name="log_purge"),
]
