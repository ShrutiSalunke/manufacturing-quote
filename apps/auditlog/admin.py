from django.contrib import admin

from .models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "event_type", "source", "message", "correlation_id")
    list_filter = ("level", "event_type", "source")
    search_fields = ("message", "traceback", "correlation_id")
    readonly_fields = (
        "level",
        "source",
        "event_type",
        "message",
        "traceback",
        "request_path",
        "http_method",
        "user",
        "correlation_id",
        "context",
        "created_at",
    )
