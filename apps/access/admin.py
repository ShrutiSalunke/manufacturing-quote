from django.contrib import admin

from .models import (
    Permission,
    Role,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "is_system", "is_active")
    list_filter = ("is_active", "is_system")
    search_fields = ("code", "name")
    inlines = [RolePermissionInline]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("module", "action", "label")
    list_filter = ("module",)
    search_fields = ("module", "action", "label")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    autocomplete_fields = ("user", "role")


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "permission", "effect")
    list_filter = ("effect",)
    autocomplete_fields = ("user", "permission")
