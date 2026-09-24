from django.urls import path

from . import views

app_name = "drawing_quote"

urlpatterns = [
    path("", views.placeholder, name="placeholder"),
]
