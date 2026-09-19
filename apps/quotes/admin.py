from django.contrib import admin

from .models import (
    Customer,
    Quote,
    QuoteCalculationSnapshot,
    QuoteDocument,
    QuoteLine,
    QuoteLineParameterValue,
)


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "company", "name", "email", "phone", "gstin", "is_active")
    list_filter = ("is_active", "country")
    search_fields = ("code", "name", "company", "email", "gstin", "phone")


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "version", "status", "customer", "plant", "created_at")
    list_filter = ("status", "plant")
    inlines = [QuoteLineInline]


admin.site.register(QuoteLineParameterValue)
admin.site.register(QuoteCalculationSnapshot)
admin.site.register(QuoteDocument)
