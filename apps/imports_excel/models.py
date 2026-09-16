from django.conf import settings
from django.db import models


class ImportJob(models.Model):
    class EntityType(models.TextChoices):
        MATERIAL = "MATERIAL", "Materials"
        MACHINE = "MACHINE", "Machines"
        LABOR = "LABOR", "Labor Roles"
        QUOTE_INPUT = "QUOTE_INPUT", "Quote Inputs"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        PARTIAL = "PARTIAL", "Partial"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    uploaded_file = models.FileField(upload_to="imports/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    row_success = models.PositiveIntegerField(default=0)
    row_failed = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="import_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entity_type} {self.status} ({self.created_at:%Y-%m-%d %H:%M})"


class ImportRowError(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="row_errors")
    row_number = models.PositiveIntegerField()
    column = models.CharField(max_length=100, blank=True, default="")
    message = models.TextField()

    class Meta:
        ordering = ["row_number"]

    def __str__(self):
        return f"Row {self.row_number}: {self.message[:60]}"
