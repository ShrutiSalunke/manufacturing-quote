from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.quote_list, name="quote_list"),
    path("new/", views.quote_create, name="quote_create"),
    path("<int:pk>/", views.quote_detail, name="quote_detail"),
    path("<int:pk>/add-line/", views.quote_add_line, name="quote_add_line"),
    path("<int:quote_pk>/lines/<int:line_pk>/parameters/", views.line_parameters, name="line_parameters"),
    path("<int:pk>/calculate/", views.quote_calculate, name="quote_calculate"),
    path("<int:pk>/pdf/", views.quote_pdf, name="quote_pdf"),
    path("<int:pk>/issue/", views.quote_issue, name="quote_issue"),
    path("<int:pk>/clone/", views.quote_clone_version, name="quote_clone"),
]
