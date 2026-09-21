from django.urls import path

from . import views, wizard_views

app_name = "quotes"

urlpatterns = [
    path("", views.quote_list, name="quote_list"),
    path("new/", wizard_views.quote_create, name="quote_create"),
    path("wizard/", wizard_views.wizard_start, name="wizard_start"),
    path("wizard/<slug:step_id>/", wizard_views.wizard_step_new, name="wizard_step_new"),
    # Specific wizard resource routes before the step slug catch-all
    path(
        "wizard/<int:quote_pk>/preview/html/",
        wizard_views.wizard_preview_html,
        name="wizard_preview_html",
    ),
    path(
        "wizard/<int:quote_pk>/preview/pdf/",
        wizard_views.wizard_preview_pdf,
        name="wizard_preview_pdf",
    ),
    path(
        "wizard/<int:quote_pk>/process-schema/",
        wizard_views.wizard_process_schema,
        name="wizard_process_schema",
    ),
    path(
        "wizard/<int:quote_pk>/process-autofill/",
        wizard_views.wizard_process_autofill,
        name="wizard_process_autofill",
    ),
    path(
        "wizard/<int:quote_pk>/process-instance/<int:qp_pk>/",
        wizard_views.wizard_process_instance,
        name="wizard_process_instance",
    ),
    path(
        "wizard/<int:quote_pk>/<slug:step_id>/",
        wizard_views.wizard_step,
        name="wizard_step",
    ),
    path("clients/suggest/", wizard_views.client_suggest, name="client_suggest"),
    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client_edit"),
    path("clients/<int:pk>/soft-delete/", views.client_soft_delete, name="client_soft_delete"),
    path("clients/<int:pk>/restore/", views.client_restore, name="client_restore"),
    path("clients/<int:pk>/permanent-delete/", views.client_permanent_delete, name="client_permanent_delete"),
    path("<int:pk>/", views.quote_detail, name="quote_detail"),
    path("<int:pk>/add-line/", views.quote_add_line, name="quote_add_line"),
    path("<int:quote_pk>/lines/<int:line_pk>/parameters/", views.line_parameters, name="line_parameters"),
    path("<int:pk>/calculate/", views.quote_calculate, name="quote_calculate"),
    path("<int:pk>/pdf/", views.quote_pdf, name="quote_pdf"),
    path("<int:pk>/preview/pdf/", views.quote_preview_pdf, name="quote_preview_pdf"),
    path("<int:pk>/issue/", views.quote_issue, name="quote_issue"),
    path("<int:pk>/clone/", views.quote_clone_version, name="quote_clone"),
    path(
        "<int:pk>/permanent-delete/",
        views.quote_permanent_delete,
        name="quote_permanent_delete",
    ),
]
