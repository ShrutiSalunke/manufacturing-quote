from django.urls import path

from . import views

app_name = "imports_excel"

urlpatterns = [
    path("", views.imports_hub, name="hub"),
    path("templates/<str:entity_type>/", views.download_template, name="download_template"),
    path("upload/<str:entity_type>/", views.upload_import, name="upload"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
]
