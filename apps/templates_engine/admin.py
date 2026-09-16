from django.contrib import admin

from .models import (
    ProductFamily,
    ProductTemplate,
    TemplateBomItem,
    TemplateCostElement,
    TemplateFormula,
    TemplateMarginRule,
    TemplateOperation,
    TemplateParameter,
)


class ParameterInline(admin.TabularInline):
    model = TemplateParameter
    extra = 0


class FormulaInline(admin.TabularInline):
    model = TemplateFormula
    extra = 0


class BomInline(admin.TabularInline):
    model = TemplateBomItem
    extra = 0


class OperationInline(admin.TabularInline):
    model = TemplateOperation
    extra = 0


class CostElementInline(admin.TabularInline):
    model = TemplateCostElement
    extra = 0


@admin.register(ProductFamily)
class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(ProductTemplate)
class ProductTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "version", "status", "plant", "family")
    list_filter = ("status", "plant")
    inlines = [ParameterInline, FormulaInline, BomInline, OperationInline, CostElementInline]


@admin.register(TemplateMarginRule)
class TemplateMarginRuleAdmin(admin.ModelAdmin):
    list_display = ("template", "method", "value_or_formula")
