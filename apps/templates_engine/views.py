from copy import deepcopy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import admin_required
from apps.costing.engine import FormulaError
from apps.costing.services import cost_template

from .forms import (
    BomItemForm,
    CostElementForm,
    FormulaForm,
    MarginRuleForm,
    OperationForm,
    ParameterForm,
    ProductTemplateForm,
    TestCalculatorForm,
)
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


@login_required
def template_list(request):
    templates = ProductTemplate.objects.select_related("family", "plant").all()
    return render(request, "templates_engine/template_list.html", {"templates": templates})


@admin_required
def template_create(request):
    if request.method == "POST":
        form = ProductTemplateForm(request.POST)
        if form.is_valid():
            tmpl = form.save()
            TemplateMarginRule.objects.get_or_create(template=tmpl)
            messages.success(request, "Product template created.")
            return redirect("templates_engine:template_detail", pk=tmpl.pk)
    else:
        form = ProductTemplateForm()
    return render(request, "templates_engine/template_form.html", {"form": form, "title": "New Product Template"})


@login_required
def template_detail(request, pk):
    tmpl = get_object_or_404(
        ProductTemplate.objects.select_related(
            "family", "plant", "margin_rule"
        ).prefetch_related(
            "parameters",
            "formulas",
            "bom_items__material",
            "operations__machine",
            "operations__labor_role",
            "cost_elements",
        ),
        pk=pk,
    )
    can_edit = request.user.is_app_admin and tmpl.status == ProductTemplate.Status.DRAFT
    test_form = TestCalculatorForm(tmpl)
    test_result = None
    if request.method == "POST" and request.POST.get("action") == "test_calc":
        test_form = TestCalculatorForm(tmpl, request.POST)
        if test_form.is_valid():
            try:
                params = test_form.parameter_values()
                qty = float(test_form.cleaned_data.get("line_qty") or 1)
                test_result = cost_template(tmpl, params, qty)
            except FormulaError as exc:
                messages.error(request, f"Calculator error: {exc}")
    return render(
        request,
        "templates_engine/template_detail.html",
        {
            "tmpl": tmpl,
            "can_edit": can_edit,
            "test_form": test_form,
            "test_result": test_result,
            "is_admin": request.user.is_app_admin,
        },
    )


@admin_required
def template_edit(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.warning(request, "Published templates are read-only. Use Save as new version.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = ProductTemplateForm(request.POST, instance=tmpl)
        if form.is_valid():
            form.save()
            messages.success(request, "Template updated.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = ProductTemplateForm(instance=tmpl)
    return render(request, "templates_engine/template_form.html", {"form": form, "title": "Edit Template"})


def _copy_template(source: ProductTemplate) -> ProductTemplate:
    latest = (
        ProductTemplate.objects.filter(plant=source.plant, code=source.code)
        .order_by("-version")
        .first()
    )
    new_version = (latest.version if latest else source.version) + 1
    with transaction.atomic():
        new = ProductTemplate.objects.create(
            family=source.family,
            plant=source.plant,
            name=source.name,
            code=source.code,
            status=ProductTemplate.Status.DRAFT,
            version=new_version,
        )
        for p in source.parameters.all():
            TemplateParameter.objects.create(
                template=new,
                code=p.code,
                label=p.label,
                data_type=p.data_type,
                unit=p.unit,
                default_value=p.default_value,
                min_value=p.min_value,
                max_value=p.max_value,
                is_required=p.is_required,
                sort_order=p.sort_order,
                help_text=p.help_text,
            )
        for f in source.formulas.all():
            TemplateFormula.objects.create(
                template=new,
                code=f.code,
                expression=f.expression,
                return_unit=f.return_unit,
                description=f.description,
                sort_order=f.sort_order,
            )
        for b in source.bom_items.all():
            TemplateBomItem.objects.create(
                template=new,
                name=b.name,
                material=b.material,
                qty_formula=b.qty_formula,
                scrap_formula=b.scrap_formula,
                cost_group=b.cost_group,
                sort_order=b.sort_order,
            )
        for o in source.operations.all():
            TemplateOperation.objects.create(
                template=new,
                sequence=o.sequence,
                name=o.name,
                machine=o.machine,
                labor_role=o.labor_role,
                setup_time_formula_min=o.setup_time_formula_min,
                cycle_time_formula_min=o.cycle_time_formula_min,
                labor_time_formula_min=o.labor_time_formula_min,
                notes=o.notes,
            )
        for c in source.cost_elements.all():
            TemplateCostElement.objects.create(
                template=new,
                code=c.code,
                name=c.name,
                category=c.category,
                amount_formula=c.amount_formula,
            )
        try:
            mr = source.margin_rule
            TemplateMarginRule.objects.create(
                template=new, method=mr.method, value_or_formula=mr.value_or_formula
            )
        except TemplateMarginRule.DoesNotExist:
            TemplateMarginRule.objects.create(template=new)
    return new


@admin_required
def template_new_version(request, pk):
    source = get_object_or_404(ProductTemplate, pk=pk)
    if request.method == "POST":
        new = _copy_template(source)
        messages.success(request, f"Created draft version {new.version}. Old quotes remain on prior versions.")
        return redirect("templates_engine:template_detail", pk=new.pk)
    return redirect("templates_engine:template_detail", pk=pk)


@admin_required
def template_publish(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if request.method == "POST":
        if not tmpl.parameters.exists():
            messages.error(request, "Add at least one parameter before publishing.")
            return redirect("templates_engine:template_detail", pk=pk)
        tmpl.status = ProductTemplate.Status.PUBLISHED
        tmpl.save(update_fields=["status", "updated_at"])
        messages.success(request, "Template published. It can now be selected on quotes.")
    return redirect("templates_engine:template_detail", pk=pk)


@admin_required
def add_parameter(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.template = tmpl
            obj.code = obj.code.upper()
            obj.save()
            messages.success(request, "Parameter added.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = ParameterForm()
    return render(request, "templates_engine/simple_form.html", {"form": form, "title": "Add Parameter", "tmpl": tmpl})


@admin_required
def add_formula(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = FormulaForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.template = tmpl
            obj.code = obj.code.upper()
            obj.save()
            messages.success(request, "Formula added.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = FormulaForm()
    return render(request, "templates_engine/simple_form.html", {"form": form, "title": "Add Formula", "tmpl": tmpl})


@admin_required
def add_bom(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = BomItemForm(request.POST, plant=tmpl.plant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.template = tmpl
            obj.save()
            messages.success(request, "BOM item added.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = BomItemForm(plant=tmpl.plant)
    return render(request, "templates_engine/simple_form.html", {"form": form, "title": "Add BOM Item", "tmpl": tmpl})


@admin_required
def add_operation(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = OperationForm(request.POST, plant=tmpl.plant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.template = tmpl
            obj.save()
            messages.success(request, "Operation added.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = OperationForm(plant=tmpl.plant)
    return render(request, "templates_engine/simple_form.html", {"form": form, "title": "Add Operation", "tmpl": tmpl})


@admin_required
def add_cost_element(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    if request.method == "POST":
        form = CostElementForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.template = tmpl
            obj.code = obj.code.upper()
            obj.save()
            messages.success(request, "Cost element added.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = CostElementForm()
    return render(
        request, "templates_engine/simple_form.html", {"form": form, "title": "Add Cost Element", "tmpl": tmpl}
    )


@admin_required
def edit_margin(request, pk):
    tmpl = get_object_or_404(ProductTemplate, pk=pk)
    if tmpl.status == ProductTemplate.Status.PUBLISHED:
        messages.error(request, "Cannot edit published template.")
        return redirect("templates_engine:template_detail", pk=pk)
    rule, _ = TemplateMarginRule.objects.get_or_create(template=tmpl)
    if request.method == "POST":
        form = MarginRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "Margin rule saved.")
            return redirect("templates_engine:template_detail", pk=pk)
    else:
        form = MarginRuleForm(instance=rule)
    return render(request, "templates_engine/simple_form.html", {"form": form, "title": "Margin Rule", "tmpl": tmpl})
