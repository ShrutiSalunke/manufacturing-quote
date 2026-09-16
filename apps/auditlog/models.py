import traceback
import uuid

from django.conf import settings
from django.db import models


class SystemLog(models.Model):
    class Level(models.TextChoices):
        DEBUG = "DEBUG", "Debug"
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        CRITICAL = "CRITICAL", "Critical"

    class EventType(models.TextChoices):
        EXCEPTION = "EXCEPTION", "Exception"
        IMPORT = "IMPORT", "Import"
        COSTING = "COSTING", "Costing"
        PDF = "PDF", "PDF"
        AUTH = "AUTH", "Auth"
        OTHER = "OTHER", "Other"

    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO, db_index=True)
    source = models.CharField(max_length=100, db_index=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.OTHER, db_index=True)
    message = models.TextField()
    traceback = models.TextField(blank=True, default="")
    request_path = models.CharField(max_length=500, blank=True, default="")
    http_method = models.CharField(max_length=10, blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="system_logs",
    )
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "level"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.source}: {self.message[:80]}"
