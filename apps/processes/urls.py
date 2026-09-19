from django.urls import path

from . import views

app_name = "processes"

urlpatterns = [
    path("", views.process_list, name="process_list"),
    path("new/", views.process_create, name="process_create"),
    path("<int:pk>/", views.process_detail, name="process_detail"),
    path("<int:pk>/edit/", views.process_edit, name="process_edit"),
    path("<int:pk>/soft-delete/", views.process_soft_delete, name="process_soft_delete"),
    path("<int:pk>/restore/", views.process_restore, name="process_restore"),
    path("<int:pk>/delete/", views.process_delete, name="process_delete"),
    path("<int:pk>/fields/new/", views.process_field_add, name="process_field_add"),
    path("<int:pk>/fields/<int:field_pk>/edit/", views.process_field_edit, name="process_field_edit"),
    path(
        "<int:pk>/fields/<int:field_pk>/delete/",
        views.process_field_delete,
        name="process_field_delete",
    ),
    path("<int:pk>/link-subprocesses/", views.process_link_subprocesses, name="process_link_subprocesses"),
    path("sub/", views.subprocess_list, name="subprocess_list"),
    path("sub/new/", views.subprocess_create, name="subprocess_create"),
    path("sub/<int:pk>/", views.subprocess_detail, name="subprocess_detail"),
    path("sub/<int:pk>/edit/", views.subprocess_edit, name="subprocess_edit"),
    path("sub/<int:pk>/soft-delete/", views.subprocess_soft_delete, name="subprocess_soft_delete"),
    path("sub/<int:pk>/restore/", views.subprocess_restore, name="subprocess_restore"),
    path("sub/<int:pk>/delete/", views.subprocess_delete, name="subprocess_delete"),
    path("sub/<int:pk>/fields/new/", views.subprocess_field_add, name="subprocess_field_add"),
    path(
        "sub/<int:pk>/fields/<int:field_pk>/edit/",
        views.subprocess_field_edit,
        name="subprocess_field_edit",
    ),
    path(
        "sub/<int:pk>/fields/<int:field_pk>/delete/",
        views.subprocess_field_delete,
        name="subprocess_field_delete",
    ),
    path("quote/<int:quote_pk>/add-process/", views.quote_add_process, name="quote_add_process"),
    path(
        "quote/<int:quote_pk>/process/<int:qp_pk>/fields/",
        views.quote_process_fields,
        name="quote_process_fields",
    ),
    path(
        "quote/<int:quote_pk>/process/<int:qp_pk>/remove/",
        views.quote_process_remove,
        name="quote_process_remove",
    ),
    path(
        "quote/<int:quote_pk>/process/<int:qp_pk>/add-subprocess/",
        views.quote_add_subprocess,
        name="quote_add_subprocess",
    ),
    path(
        "quote/<int:quote_pk>/process/<int:qp_pk>/subprocess/<int:qs_pk>/fields/",
        views.quote_subprocess_fields,
        name="quote_subprocess_fields",
    ),
    path(
        "quote/<int:quote_pk>/process/<int:qp_pk>/subprocess/<int:qs_pk>/remove/",
        views.quote_subprocess_remove,
        name="quote_subprocess_remove",
    ),
]
