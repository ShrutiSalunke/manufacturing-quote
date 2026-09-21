from django.urls import path

from . import views

app_name = "access"

urlpatterns = [
    path("", views.access_hub, name="hub"),
    path(
        "roles/<int:role_pk>/permissions/",
        views.role_save_permissions,
        name="role_save_permissions",
    ),
    path(
        "roles/<int:role_pk>/assign/",
        views.role_assign_user,
        name="role_assign_user",
    ),
    path(
        "roles/<int:role_pk>/members/<int:user_pk>/remove/",
        views.role_remove_user,
        name="role_remove_user",
    ),
]
