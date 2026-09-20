from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("materials/", views.material_list, name="material_list"),
    path("materials/new/", views.material_create, name="material_create"),
    path("materials/<int:pk>/", views.material_detail, name="material_detail"),
    path("materials/<int:pk>/edit/", views.material_edit, name="material_edit"),
    path("materials/<int:pk>/soft-delete/", views.material_soft_delete, name="material_soft_delete"),
    path("materials/<int:pk>/restore/", views.material_restore, name="material_restore"),
    path(
        "materials/<int:pk>/permanent-delete/",
        views.material_permanent_delete,
        name="material_permanent_delete",
    ),
    path("machines/", views.machine_list, name="machine_list"),
    path("machines/new/", views.machine_create, name="machine_create"),
    path("machines/<int:pk>/", views.machine_detail, name="machine_detail"),
    path("machines/<int:pk>/edit/", views.machine_edit, name="machine_edit"),
    path("machines/<int:pk>/soft-delete/", views.machine_soft_delete, name="machine_soft_delete"),
    path("machines/<int:pk>/restore/", views.machine_restore, name="machine_restore"),
    path(
        "machines/<int:pk>/permanent-delete/",
        views.machine_permanent_delete,
        name="machine_permanent_delete",
    ),
    path("labor/", views.labor_list, name="labor_list"),
    path("labor/new/", views.labor_create, name="labor_create"),
    path("labor/<int:pk>/", views.labor_detail, name="labor_detail"),
    path("labor/<int:pk>/edit/", views.labor_edit, name="labor_edit"),
    path("labor/<int:pk>/soft-delete/", views.labor_soft_delete, name="labor_soft_delete"),
    path("labor/<int:pk>/restore/", views.labor_restore, name="labor_restore"),
    path(
        "labor/<int:pk>/permanent-delete/",
        views.labor_permanent_delete,
        name="labor_permanent_delete",
    ),
    path("custom-fields/", views.custom_field_list, name="custom_field_list"),
    path("custom-fields/new/", views.custom_field_create, name="custom_field_create"),
    path("custom-fields/<int:pk>/", views.custom_field_detail, name="custom_field_detail"),
    path("custom-fields/<int:pk>/edit/", views.custom_field_edit, name="custom_field_edit"),
    path(
        "custom-fields/<int:pk>/soft-delete/",
        views.custom_field_soft_delete,
        name="custom_field_soft_delete",
    ),
    path("custom-fields/<int:pk>/restore/", views.custom_field_restore, name="custom_field_restore"),
    path(
        "custom-fields/<int:pk>/permanent-delete/",
        views.custom_field_permanent_delete,
        name="custom_field_permanent_delete",
    ),
]
