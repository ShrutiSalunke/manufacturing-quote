from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import admin_required

from .forms import CustomFieldForm
from .models import CustomFieldDefinition, LaborRole, Machine, Material


@login_required
def material_list(request):
    materials = Material.objects.select_related("plant").all()
    return render(request, "catalog/material_list.html", {"materials": materials})


@login_required
def material_detail(request, pk):
    material = get_object_or_404(Material.objects.select_related("plant"), pk=pk)
    return render(request, "catalog/material_detail.html", {"material": material})


@login_required
def machine_list(request):
    machines = Machine.objects.select_related("plant").all()
    return render(request, "catalog/machine_list.html", {"machines": machines})


@login_required
def labor_list(request):
    roles = LaborRole.objects.select_related("plant").all()
    return render(request, "catalog/labor_list.html", {"roles": roles})


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
            messages.success(request, "Custom field created. Excel templates will include it on next download.")
            return redirect("catalog:custom_field_list")
    else:
        form = CustomFieldForm()
    return render(request, "catalog/custom_field_form.html", {"form": form, "title": "Add Custom Field"})


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
    return render(request, "catalog/custom_field_form.html", {"form": form, "title": "Edit Custom Field"})


@admin_required
def custom_field_toggle(request, pk):
    field = get_object_or_404(CustomFieldDefinition, pk=pk)
    if request.method == "POST":
        field.is_active = not field.is_active
        field.save(update_fields=["is_active"])
        messages.info(request, f"Custom field '{field.key}' is now {'active' if field.is_active else 'inactive'}.")
    return redirect("catalog:custom_field_list")
