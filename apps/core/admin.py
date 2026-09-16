from django.contrib import admin

from .models import AppSetting, Plant


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "currency", "timezone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description")
