from django.contrib import admin

from .models import ImportJob, ImportRowError


class RowErrorInline(admin.TabularInline):
    model = ImportRowError
    extra = 0
    readonly_fields = ("row_number", "column", "message")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "status", "row_success", "row_failed", "created_at", "created_by")
    list_filter = ("entity_type", "status")
    inlines = [RowErrorInline]
