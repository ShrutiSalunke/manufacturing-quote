from django.contrib import admin

from .models import CustomFieldDefinition, CustomFieldValue, LaborRole, Machine, Material


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "unit_price", "uom", "is_active")
    list_filter = ("plant", "is_active", "category")
    search_fields = ("code", "name")


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "hourly_rate", "efficiency_percent", "is_active")
    list_filter = ("plant", "is_active")


@admin.register(LaborRole)
class LaborRoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "hourly_rate", "is_active")
    list_filter = ("plant", "is_active")


@admin.register(CustomFieldDefinition)
class CustomFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "label",
        "entity_type",
        "data_type",
        "is_importable",
        "is_active",
        "plant",
    )
    list_filter = ("entity_type", "is_active", "is_importable")


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ("definition", "content_type", "object_id", "value_text", "value_number")
