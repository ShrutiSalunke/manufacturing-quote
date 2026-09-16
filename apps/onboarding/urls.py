from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    path("status/", views.tour_status, name="tour_status"),
    path("complete/", views.tour_complete, name="tour_complete"),
    path("dismiss/", views.tour_dismiss, name="tour_dismiss"),
    path("step/", views.tour_step, name="tour_step"),
    path("restart/", views.restart_tour, name="restart_tour"),
]
