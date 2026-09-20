from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import admin_required

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


def _list_page(request, qs, *, search_fields, list_url_name, panel_template, page_template, context_key):
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
    context = {
        "page_obj": page_obj,
        context_key: page_obj.object_list,
        "q": q,
        "active": active,
        "per_page": per_page,
        "per_page_choices": PER_PAGE_CHOICES,
        "page_numbers": _page_number_window(page_obj),
        "list_url_name": list_url_name,
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


# —— Materials ——


@login_required
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
    )


@login_required
def material_detail(request, pk):
    material = get_object_or_404(Material.objects.select_related("plant"), pk=pk)
    return render(request, "catalog/material_detail.html", {"material": material})


@admin_required
def material_create(request):
    if request.method == "POST":
        form = MaterialForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=MaterialForm(instance=obj),
                title="Add Material",
                obj=obj,
                success_message=f"Material {obj.code} created.",
                success_redirect=reverse("catalog:material_list"),
                template="catalog/material_form.html",
            )
    else:
        form = MaterialForm(initial={"is_active": True, "currency": "INR", "uom": "kg"})
    return render(request, "catalog/material_form.html", {"form": form, "title": "Add Material"})


@admin_required
def material_edit(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        form = MaterialForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=MaterialForm(instance=obj),
                title="Edit Material",
                obj=obj,
                success_message=f"Material {obj.code} updated.",
                success_redirect=reverse("catalog:material_list"),
                template="catalog/material_form.html",
            )
    else:
        form = MaterialForm(instance=obj)
    return render(
        request,
        "catalog/material_form.html",
        {"form": form, "title": "Edit Material", "object": obj},
    )


@admin_required
def material_soft_delete(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Material {obj.code} set to Inactive.")
        else:
            messages.info(request, f"Material {obj.code} is already inactive.")
    return redirect("catalog:material_list")


@admin_required
def material_restore(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Material {obj.code} restored (Active).")
        else:
            messages.info(request, f"Material {obj.code} is already active.")
    return redirect("catalog:material_list")


@admin_required
def material_permanent_delete(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Material {code} permanently deleted.")
    return redirect("catalog:material_list")


# —— Machines ——


@login_required
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
    )


@login_required
def machine_detail(request, pk):
    machine = get_object_or_404(Machine.objects.select_related("plant"), pk=pk)
    return render(request, "catalog/machine_detail.html", {"machine": machine})


@admin_required
def machine_create(request):
    if request.method == "POST":
        form = MachineForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=MachineForm(instance=obj),
                title="Add Machine",
                obj=obj,
                success_message=f"Machine {obj.code} created.",
                success_redirect=reverse("catalog:machine_list"),
                template="catalog/machine_form.html",
            )
    else:
        form = MachineForm(initial={"is_active": True, "efficiency_percent": 100})
    return render(request, "catalog/machine_form.html", {"form": form, "title": "Add Machine"})


@admin_required
def machine_edit(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    if request.method == "POST":
        form = MachineForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=MachineForm(instance=obj),
                title="Edit Machine",
                obj=obj,
                success_message=f"Machine {obj.code} updated.",
                success_redirect=reverse("catalog:machine_list"),
                template="catalog/machine_form.html",
            )
    else:
        form = MachineForm(instance=obj)
    return render(
        request,
        "catalog/machine_form.html",
        {"form": form, "title": "Edit Machine", "object": obj},
    )


@admin_required
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


@admin_required
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


@admin_required
def machine_permanent_delete(request, pk):
    obj = get_object_or_404(Machine, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Machine {code} permanently deleted.")
    return redirect("catalog:machine_list")


# —— Labor roles ——


@login_required
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
    )


@login_required
def labor_detail(request, pk):
    role = get_object_or_404(LaborRole.objects.select_related("plant"), pk=pk)
    return render(request, "catalog/labor_detail.html", {"role": role})


@admin_required
def labor_create(request):
    if request.method == "POST":
        form = LaborRoleForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=LaborRoleForm(instance=obj),
                title="Add Labor Role",
                obj=obj,
                success_message=f"Labor role {obj.code} created.",
                success_redirect=reverse("catalog:labor_list"),
                template="catalog/labor_form.html",
            )
    else:
        form = LaborRoleForm(initial={"is_active": True})
    return render(request, "catalog/labor_form.html", {"form": form, "title": "Add Labor Role"})


@admin_required
def labor_edit(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    if request.method == "POST":
        form = LaborRoleForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            return _form_success(
                request,
                form=LaborRoleForm(instance=obj),
                title="Edit Labor Role",
                obj=obj,
                success_message=f"Labor role {obj.code} updated.",
                success_redirect=reverse("catalog:labor_list"),
                template="catalog/labor_form.html",
            )
    else:
        form = LaborRoleForm(instance=obj)
    return render(
        request,
        "catalog/labor_form.html",
        {"form": form, "title": "Edit Labor Role", "object": obj},
    )


@admin_required
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


@admin_required
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


@admin_required
def labor_permanent_delete(request, pk):
    obj = get_object_or_404(LaborRole, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Labor role {code} permanently deleted.")
    return redirect("catalog:labor_list")


# —— Custom fields (unchanged behaviour) ——


@admin_required
def custom_field_list(request):
    fields = CustomFieldDefinition.objects.select_related("plant").all()
    return render(request, "catalog/custom_field_list.html", {"fields": fields})


@admin_required
def custom_field_create(request):
    if request.method == "POST":
        form = CustomFieldForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Custom field created. Excel templates will include it on next download.",
            )
            return redirect("catalog:custom_field_list")
    else:
        form = CustomFieldForm()
    return render(
        request, "catalog/custom_field_form.html", {"form": form, "title": "Add Custom Field"}
    )


@admin_required
def custom_field_edit(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        form = CustomFieldForm(request.POST, instance=field)
        if form.is_valid():
            form.save()
            messages.success(request, "Custom field updated.")
            return redirect("catalog:custom_field_list")
    else:
        form = CustomFieldForm(instance=field)
    return render(
        request, "catalog/custom_field_form.html", {"form": form, "title": "Edit Custom Field"}
    )


@admin_required
def custom_field_toggle(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        field.is_active = not field.is_active
        field.save(update_fields=["is_active"])
        messages.info(
            request,
            f"Custom field '{field.key}' is now {'active' if field.is_active else 'inactive'}.",
        )
    return redirect("catalog:custom_field_list")
