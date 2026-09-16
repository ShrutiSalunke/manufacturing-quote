from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("materials/", views.material_list, name="material_list"),
    path("materials/<int:pk>/", views.material_detail, name="material_detail"),
    path("machines/", views.machine_list, name="machine_list"),
    path("labor/", views.labor_list, name="labor_list"),
    path("custom-fields/", views.custom_field_list, name="custom_field_list"),
    path("custom-fields/new/", views.custom_field_create, name="custom_field_create"),
    path("custom-fields/<int:pk>/edit/", views.custom_field_edit, name="custom_field_edit"),
    path("custom-fields/<int:pk>/toggle/", views.custom_field_toggle, name="custom_field_toggle"),
]
