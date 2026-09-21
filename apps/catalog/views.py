from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm

from . import custom_fields as cf
from .forms import CustomFieldForm, LaborRoleForm, MachineForm, MaterialForm
from .models import CustomFieldDefinition, LaborRole, Machine, Material

PER_PAGE_CHOICES = (10, 15, 25, 50)
DEFAULT_PER_PAGE = 15


def _page_number_window(page_obj, adjacent=1):
    current = page_obj.number
    total = page_obj.paginator.num_pages
    if total <= 7:
        return list(range(1, total + 1))
    pages = {1, total, current}
    for i in range(current - adjacent, current + adjacent + 1):
        if 1 <= i <= total:
            pages.add(i)
    ordered = sorted(pages)
    result = []
    prev = None
    for num in ordered:
        if prev is not None and num - prev > 1:
            result.append(None)
        result.append(num)
        prev = num
    return result


def _list_page(
    request,
    qs,
    *,
    search_fields,
    list_url_name,
    panel_template,
    page_template,
    context_key,
    entity_type=None,
):
    q = (request.GET.get("q") or "").strip()
    active = request.GET.get("active") or ""
    if q:
        clause = Q()
        for field in search_fields:
            clause |= Q(**{f"{field}__icontains": q})
        qs = qs.filter(clause)
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)

    try:
        per_page = int(request.GET.get("per_page") or DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    if per_page not in PER_PAGE_CHOICES:
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = list(page_obj.object_list)
    custom_columns = []
    if entity_type:
        custom_columns = cf.active_definitions(entity_type)
        rows = cf.attach_custom_columns(rows, custom_columns)
    context = {
        "page_obj": page_obj,
        context_key: rows,
        "q": q,
        "active": active,
        "per_page": per_page,
        "per_page_choices": PER_PAGE_CHOICES,
        "page_numbers": _page_number_window(page_obj),
        "list_url_name": list_url_name,
        "custom_columns": custom_columns,
    }
    template = panel_template if getattr(request, "htmx", False) else page_template
    return render(request, template, context)


def _form_success(request, *, form, title, obj, success_message, success_redirect, template, context_extra=None):
    ctx = {
        "form": form,
        "title": title,
        "object": obj,
        "success_message": success_message,
        "success_redirect": success_redirect,
    }
    if context_extra:
        ctx.update(context_extra)
    return render(request, template, ctx)


def _defs_for_entity(entity_type, obj=None, post_data=None, form_class=None):
    """Resolve which custom definitions apply (plant-aware when possible)."""
    plant = None
    if obj is not None and getattr(obj, "plant_id", None):
        plant = obj.plant
    elif post_data is not None and form_class is not None:
        # Peek plant from posted master form without full validation.
        try:
            plant_id = int(post_data.get("plant") or 0) or None
        except (TypeError, ValueError):
            plant_id = None
        if plant_id:
            from apps.core.models import Plant

            plant = Plant.objects.filter(pk=plant_id).first()
    return cf.active_definitions(entity_type, plant=plant)


def _save_master_with_custom(
    request,
    *,
    form_class,
    entity_type,
    template,
    title,
    list_url_name,
    success_label,
    instance=None,
    initial=None,
):
    """Shared create/edit for Material / Machine / Labor with custom columns."""
    obj = instance
    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        definitions = _defs_for_entity(
            entity_type, obj=instance, post_data=request.POST, form_class=form_class
        )
        # After plant is known from a valid form, refine definitions.
        cf_form = cf.CustomFieldValuesForm(
            request.POST, definitions=definitions, instance=instance
        )
        if form.is_valid():
            definitions = cf.active_definitions(entity_type, plant=form.cleaned_data.get("plant"))
            cf_form = cf.CustomFieldValuesForm(
                request.POST, definitions=definitions, instance=instance
            )
            if cf_form.is_valid():
                obj = form.save()
                cf.save_custom_field_values(obj, cf_form.cleaned_data, definitions)
                definitions = cf.active_definitions(entity_type, plant=obj.plant)
                return _form_success(
                    request,
                    form=form_class(instance=obj),
                    title=title,
                    obj=obj,
                    success_message=f"{success_label} {obj.code} {'updated' if instance else 'created'}.",
                    success_redirect=reverse(list_url_name),
                    template=template,
                    context_extra={
                        "cf_form": cf.CustomFieldValuesForm(
                            definitions=definitions, instance=obj
                        ),
                        "custom_definitions": definitions,
                    },
                )
    else:
        form = form_class(instance=instance, initial=initial)
        definitions = _defs_for_entity(entity_type, obj=instance)
        cf_form = cf.CustomFieldValuesForm(definitions=definitions, instance=instance)

    return render(
        request,
        template,
        {
            "form": form,
            "cf_form": cf_form,
            "custom_definitions": getattr(cf_form, "definitions", []),
            "title": title,
            "object": obj,
        },
    )


# —— Materials ——


@require_perm("materials", "view")
def material_list(request):
    qs = Material.objects.select_related("plant").order_by("code")
    return _list_page(
        request,
        qs,
        search_fields=("code", "name", "category", "plant__code", "plant__name"),
        list_url_name="catalog:material_list",
        panel_template="catalog/partials/material_table_panel.html",
        page_template="catalog/material_list.html",
        context_key="materials",
        entity_type=CustomFieldDefinition.EntityType.MATERIAL,
    )


@require_perm("materials", "view")
def material_detail(request, pk):
    material = get_object_or_404(Material.objects.select_related("plant"), pk=pk)
    definitions = cf.active_definitions(
        CustomFieldDefinition.EntityType.MATERIAL, plant=material.plant
    )
    return render(
        request,
        "catalog/material_detail.html",
        {
            "material": material,
            "custom_rows": cf.detail_rows(material, definitions),
        },
    )


@require_perm("materials", "create")
def material_create(request):
    return _save_master_with_custom(
        request,
        form_class=MaterialForm,
        entity_type=CustomFieldDefinition.EntityType.MATERIAL,
        template="catalog/material_form.html",
        title="Add Material",
        list_url_name="catalog:material_list",
        success_label="Material",
        initial={"is_active": True, "currency": "INR", "uom": "kg"},
    )


@require_perm("materials", "edit")
def material_edit(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    return _save_master_with_custom(
        request,
        form_class=MaterialForm,
        entity_type=CustomFieldDefinition.EntityType.MATERIAL,
        template="catalog/material_form.html",
        title="Edit Material",
        list_url_name="catalog:material_list",
        success_label="Material",
        instance=obj,
    )


def _safe_material_next(request, pk):
    """Only allow redirect back to this material's detail URL."""
    next_url = (request.POST.get("next") or "").strip()
    detail = reverse("catalog:material_detail", args=[pk])
    if next_url == detail or next_url.startswith(detail + "?"):
        return next_url
    return None


@require_perm("materials", "soft_delete")
def material_soft_delete(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                f"Material {obj.code} soft-deleted (set to Inactive). Existing quotes keep this material.",
            )
        else:
            messages.info(request, f"Material {obj.code} is already inactive.")
    return redirect(_safe_material_next(request, pk) or "catalog:material_list")


@require_perm("materials", "soft_delete")
def material_restore(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Material {obj.code} restored (Active).")
        else:
            messages.info(request, f"Material {obj.code} is already active.")
    return redirect(_safe_material_next(request, pk) or "catalog:material_list")


@require_perm("materials", "permanent_delete")
def material_permanent_delete(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(
            request,
            f"Material {code} permanently deleted. Quote links to this material were cleared.",
        )
        return redirect("catalog:material_list")
    return redirect("catalog:material_detail", pk=pk)


# —— Machines ——


@require_perm("machines", "view")
def machine_list(request):
    qs = Machine.objects.select_related("plant").order_by("code")
    return _list_page(
        request,
        qs,
        search_fields=("code", "name", "plant__code", "plant__name"),
        list_url_name="catalog:machine_list",
        panel_template="catalog/partials/machine_table_panel.html",
        page_template="catalog/machine_list.html",
        context_key="machines",
        entity_type=CustomFieldDefinition.EntityType.MACHINE,
    )


@require_perm("machines", "view")
def machine_detail(request, pk):
    machine = get_object_or_404(Machine.objects.select_related("plant"), pk=pk)
    definitions = cf.active_definitions(
        CustomFieldDefinition.EntityType.MACHINE, plant=machine.plant
    )
    return render(
        request,
        "catalog/machine_detail.html",
        {
            "machine": machine,
            "custom_rows": cf.detail_rows(machine, definitions),
        },
    )


@require_perm("machines", "create")
def machine_create(request):
    return _save_master_with_custom(
        request,
        form_class=MachineForm,
        entity_type=CustomFieldDefinition.EntityType.MACHINE,
        template="catalog/machine_form.html",
        title="Add Machine",
        list_url_name="catalog:machine_list",
        success_label="Machine",
        initial={"is_active": True, "efficiency_percent": 100},
    )


@require_perm("machines", "edit")
def machine_edit(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    return _save_master_with_custom(
        request,
        form_class=MachineForm,
        entity_type=CustomFieldDefinition.EntityType.MACHINE,
        template="catalog/machine_form.html",
        title="Edit Machine",
        list_url_name="catalog:machine_list",
        success_label="Machine",
        instance=obj,
    )


@require_perm("machines", "soft_delete")
def machine_soft_delete(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Machine {obj.code} set to Inactive.")
        else:
            messages.info(request, f"Machine {obj.code} is already inactive.")
    return redirect("catalog:machine_list")


@require_perm("machines", "soft_delete")
def machine_restore(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Machine {obj.code} restored (Active).")
        else:
            messages.info(request, f"Machine {obj.code} is already active.")
    return redirect("catalog:machine_list")


@require_perm("machines", "permanent_delete")
def machine_permanent_delete(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Machine {code} permanently deleted.")
    return redirect("catalog:machine_list")


# —— Labor roles ——


@require_perm("labor", "view")
def labor_list(request):
    qs = LaborRole.objects.select_related("plant").order_by("code")
    return _list_page(
        request,
        qs,
        search_fields=("code", "name", "plant__code", "plant__name"),
        list_url_name="catalog:labor_list",
        panel_template="catalog/partials/labor_table_panel.html",
        page_template="catalog/labor_list.html",
        context_key="roles",
        entity_type=CustomFieldDefinition.EntityType.LABOR,
    )


@require_perm("labor", "view")
def labor_detail(request, pk):
    role = get_object_or_404(LaborRole.objects.select_related("plant"), pk=pk)
    definitions = cf.active_definitions(
        CustomFieldDefinition.EntityType.LABOR, plant=role.plant
    )
    return render(
        request,
        "catalog/labor_detail.html",
        {
            "role": role,
            "custom_rows": cf.detail_rows(role, definitions),
        },
    )


@require_perm("labor", "create")
def labor_create(request):
    return _save_master_with_custom(
        request,
        form_class=LaborRoleForm,
        entity_type=CustomFieldDefinition.EntityType.LABOR,
        template="catalog/labor_form.html",
        title="Add Labor Role",
        list_url_name="catalog:labor_list",
        success_label="Labor role",
        initial={"is_active": True},
    )


@require_perm("labor", "edit")
def labor_edit(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    return _save_master_with_custom(
        request,
        form_class=LaborRoleForm,
        entity_type=CustomFieldDefinition.EntityType.LABOR,
        template="catalog/labor_form.html",
        title="Edit Labor Role",
        list_url_name="catalog:labor_list",
        success_label="Labor role",
        instance=obj,
    )


@require_perm("labor", "soft_delete")
def labor_soft_delete(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Labor role {obj.code} set to Inactive.")
        else:
            messages.info(request, f"Labor role {obj.code} is already inactive.")
    return redirect("catalog:labor_list")


@require_perm("labor", "soft_delete")
def labor_restore(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Labor role {obj.code} restored (Active).")
        else:
            messages.info(request, f"Labor role {obj.code} is already active.")
    return redirect("catalog:labor_list")


@require_perm("labor", "permanent_delete")
def labor_permanent_delete(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Labor role {code} permanently deleted.")
    return redirect("catalog:labor_list")


# —— Custom fields ——


@require_perm("custom_fields", "view")
def custom_field_list(request):
    fields = CustomFieldDefinition.objects.select_related("plant").order_by(
        "entity_type", "sort_order", "key"
    )
    return render(request, "catalog/custom_field_list.html", {"fields": fields})


@require_perm("custom_fields", "view")
def custom_field_detail(request, pk):
    field = get_object_or_404(CustomFieldDefinition.objects.select_related("plant"), pk=pk)
    return render(request, "catalog/custom_field_detail.html", {"field": field})


@require_perm("custom_fields", "create")
def custom_field_create(request):
    if request.method == "POST":
        form = CustomFieldForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(
                request,
                f"Custom column “{obj.label}” added to {obj.get_entity_type_display()}. "
                "It now appears on that table, forms, and Excel templates.",
            )
            return redirect("catalog:custom_field_list")
    else:
        form = CustomFieldForm(
            initial={
                "is_active": True,
                "is_importable": True,
                "data_type": CustomFieldDefinition.DataType.TEXT,
            }
        )
    return render(
        request, "catalog/custom_field_form.html", {"form": form, "title": "Add Custom Column"}
    )


@require_perm("custom_fields", "edit")
def custom_field_edit(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        form = CustomFieldForm(request.POST, instance=field)
        if form.is_valid():
            form.save()
            messages.success(request, "Custom column updated.")
            return redirect("catalog:custom_field_list")
    else:
        form = CustomFieldForm(instance=field)
    return render(
        request,
        "catalog/custom_field_form.html",
        {"form": form, "title": "Edit Custom Column", "object": field},
    )


def _safe_custom_field_next(request, pk):
    next_url = (request.POST.get("next") or "").strip()
    detail = reverse("catalog:custom_field_detail", args=[pk])
    if next_url == detail or next_url.startswith(detail + "?"):
        return next_url
    return None


@require_perm("custom_fields", "soft_delete")
def custom_field_soft_delete(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        if field.is_active:
            field.is_active = False
            field.save(update_fields=["is_active"])
            messages.success(
                request,
                f"Custom column “{field.label}” soft-deleted (set to Inactive). "
                "It is hidden from master tables until restored.",
            )
        else:
            messages.info(request, f"Custom column “{field.label}” is already inactive.")
    return redirect(_safe_custom_field_next(request, pk) or "catalog:custom_field_list")


@require_perm("custom_fields", "soft_delete")
def custom_field_restore(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        if not field.is_active:
            field.is_active = True
            field.save(update_fields=["is_active"])
            messages.success(request, f"Custom column “{field.label}” restored (Active).")
        else:
            messages.info(request, f"Custom column “{field.label}” is already active.")
    return redirect(_safe_custom_field_next(request, pk) or "catalog:custom_field_list")


@require_perm("custom_fields", "permanent_delete")
def custom_field_permanent_delete(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        label = field.label
        field.delete()
        messages.success(
            request,
            f"Custom column “{label}” permanently deleted. Saved values for that column were removed.",
        )
        return redirect("catalog:custom_field_list")
    return redirect("catalog:custom_field_detail", pk=pk)
