from django.urls import path

from . import views

app_name = "templates_engine"

urlpatterns = [
    path("", views.template_list, name="template_list"),
    path("new/", views.template_create, name="template_create"),
    path("<int:pk>/", views.template_detail, name="template_detail"),
    path("<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("<int:pk>/publish/", views.template_publish, name="template_publish"),
    path("<int:pk>/new-version/", views.template_new_version, name="template_new_version"),
    path("<int:pk>/parameters/add/", views.add_parameter, name="add_parameter"),
    path("<int:pk>/formulas/add/", views.add_formula, name="add_formula"),
    path("<int:pk>/bom/add/", views.add_bom, name="add_bom"),
    path("<int:pk>/operations/add/", views.add_operation, name="add_operation"),
    path("<int:pk>/cost-elements/add/", views.add_cost_element, name="add_cost_element"),
    path("<int:pk>/margin/", views.edit_margin, name="edit_margin"),
]
