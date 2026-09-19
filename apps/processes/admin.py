from django.contrib import admin

from .models import (
    Process,
    ProcessField,
    ProcessSubProcessLink,
    QuoteProcess,
    QuoteProcessFieldValue,
    QuoteSubProcess,
    QuoteSubProcessFieldValue,
    SubProcess,
    SubProcessField,
)


class ProcessFieldInline(admin.TabularInline):
    model = ProcessField
    extra = 0


class ProcessSubProcessLinkInline(admin.TabularInline):
    model = ProcessSubProcessLink
    extra = 0
    fk_name = "process"


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "result_unit", "is_active", "use_material_properties")
    list_filter = ("plant", "is_active", "result_unit")
    search_fields = ("code", "name")
    inlines = [ProcessFieldInline, ProcessSubProcessLinkInline]


class SubProcessFieldInline(admin.TabularInline):
    model = SubProcessField
    extra = 0


@admin.register(SubProcess)
class SubProcessAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "result_unit", "is_active", "use_material_properties")
    list_filter = ("plant", "is_active", "result_unit")
    search_fields = ("code", "name")
    inlines = [SubProcessFieldInline]


class QuoteProcessFieldValueInline(admin.TabularInline):
    model = QuoteProcessFieldValue
    extra = 0


class QuoteSubProcessInline(admin.TabularInline):
    model = QuoteSubProcess
    extra = 0
    show_change_link = True


@admin.register(QuoteProcess)
class QuoteProcessAdmin(admin.ModelAdmin):
    list_display = ("quote", "process", "material", "computed_own", "computed_total")
    inlines = [QuoteProcessFieldValueInline, QuoteSubProcessInline]


class QuoteSubProcessFieldValueInline(admin.TabularInline):
    model = QuoteSubProcessFieldValue
    extra = 0


@admin.register(QuoteSubProcess)
class QuoteSubProcessAdmin(admin.ModelAdmin):
    list_display = ("quote_process", "subprocess", "computed_value")
    inlines = [QuoteSubProcessFieldValueInline]
