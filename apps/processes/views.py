from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import admin_required
from apps.quotes.models import Quote

from .forms import (
    ProcessFieldForm,
    ProcessFieldFormSet,
    ProcessForm,
    ProcessLinkSubProcessesForm,
    QuoteAddProcessForm,
    QuoteAddSubProcessForm,
    SubProcessFieldForm,
    SubProcessFieldFormSet,
    SubProcessForm,
    apply_formula_field_validation,
    build_dynamic_field_form,
)
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
from .services import calculate_quote_process

MASTER_PER_PAGE_CHOICES = (10, 15, 25, 50)
MASTER_DEFAULT_PER_PAGE = 15


def _in_quote_wizard(request) -> bool:
    return request.GET.get("wizard") == "1" or request.POST.get("wizard") == "1"


def _wizard_qs(request) -> str:
    return "?wizard=1" if _in_quote_wizard(request) else ""


def _redirect_quote_home(request, quote_pk):
    """Return to wizard processes step or quote detail after process edits."""
    if _in_quote_wizard(request):
        return redirect("quotes:wizard_step", quote_pk=quote_pk, step_id="processes")
    return redirect("quotes:quote_detail", pk=quote_pk)


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


def _master_list(request, qs, *, search_fields, panel_partial, full_template, context_list_key):
    q = (request.GET.get("q") or "").strip()
    active = request.GET.get("active") or ""
    if q:
        query = Q()
        for field in search_fields:
            query |= Q(**{f"{field}__icontains": q})
        qs = qs.filter(query)
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)

    try:
        per_page = int(request.GET.get("per_page") or MASTER_DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = MASTER_DEFAULT_PER_PAGE
    if per_page not in MASTER_PER_PAGE_CHOICES:
        per_page = MASTER_DEFAULT_PER_PAGE

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        context_list_key: page_obj.object_list,
        "q": q,
        "active": active,
        "per_page": per_page,
        "per_page_choices": MASTER_PER_PAGE_CHOICES,
        "page_numbers": _page_number_window(page_obj),
    }
    template = panel_partial if getattr(request, "htmx", False) else full_template
    return render(request, template, context)


@login_required
def process_list(request):
    qs = Process.objects.select_related("plant").order_by("code")
    return _master_list(
        request,
        qs,
        search_fields=("code", "name", "description", "plant__code", "plant__name"),
        panel_partial="processes/partials/process_table_panel.html",
        full_template="processes/process_list.html",
        context_list_key="items",
    )


@admin_required
def process_create(request):
    if request.method == "POST":
        form = ProcessForm(request.POST)
        formset = ProcessFieldFormSet(request.POST)
        if form.is_valid() and formset.is_valid() and apply_formula_field_validation(form, formset):
            obj = form.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f"Process {obj.code} created.")
            return redirect("processes:process_detail", pk=obj.pk)
    else:
        form = ProcessForm(initial={"is_active": True, "result_formula": "0"})
        formset = ProcessFieldFormSet()
    return render(
        request,
        "processes/process_form.html",
        {"form": form, "formset": formset, "title": "Add Process"},
    )


@login_required
def process_detail(request, pk):
    obj = get_object_or_404(
        Process.objects.select_related("plant").prefetch_related("fields", "subprocesses"),
        pk=pk,
    )
    return render(request, "processes/process_detail.html", {"process": obj})


@admin_required
def process_edit(request, pk):
    obj = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        form = ProcessForm(request.POST, instance=obj)
        formset = ProcessFieldFormSet(request.POST, instance=obj)
        if form.is_valid() and formset.is_valid() and apply_formula_field_validation(form, formset):
            form.save()
            formset.save()
            messages.success(request, f"Process {obj.code} updated.")
            return redirect("processes:process_detail", pk=pk)
    else:
        form = ProcessForm(instance=obj)
        formset = ProcessFieldFormSet(instance=obj)
    return render(
        request,
        "processes/process_form.html",
        {"form": form, "formset": formset, "title": "Edit Process", "process": obj},
    )


@admin_required
def process_soft_delete(request, pk):
    obj = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Process {obj.code} set to Inactive.")
        else:
            messages.info(request, f"Process {obj.code} is already inactive.")
    return redirect("processes:process_list")


@admin_required
def process_restore(request, pk):
    obj = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Process {obj.code} restored (Active).")
        else:
            messages.info(request, f"Process {obj.code} is already active.")
    return redirect("processes:process_list")


@admin_required
def process_delete(request, pk):
    obj = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Process {code} permanently deleted.")
        return redirect("processes:process_list")
    return redirect("processes:process_detail", pk=pk)


@admin_required
def process_field_add(request, pk):
    process = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        form = ProcessFieldForm(request.POST)
        if form.is_valid():
            field = form.save(commit=False)
            field.process = process
            field.save()
            messages.success(request, f"Field {field.code} added.")
            return redirect("processes:process_detail", pk=pk)
    else:
        form = ProcessFieldForm()
    return render(
        request,
        "processes/field_form.html",
        {
            "form": form,
            "title": "Add Process Field",
            "back_url": reverse("processes:process_detail", args=[pk]),
        },
    )


@admin_required
def process_field_edit(request, pk, field_pk):
    process = get_object_or_404(Process, pk=pk)
    field = get_object_or_404(ProcessField, pk=field_pk, process=process)
    if request.method == "POST":
        form = ProcessFieldForm(request.POST, instance=field)
        if form.is_valid():
            form.save()
            messages.success(request, f"Field {field.code} updated.")
            return redirect("processes:process_detail", pk=pk)
    else:
        form = ProcessFieldForm(instance=field)
    return render(
        request,
        "processes/field_form.html",
        {
            "form": form,
            "title": "Edit Process Field",
            "back_url": reverse("processes:process_detail", args=[pk]),
        },
    )


@admin_required
def process_field_delete(request, pk, field_pk):
    process = get_object_or_404(Process, pk=pk)
    field = get_object_or_404(ProcessField, pk=field_pk, process=process)
    if request.method == "POST":
        code = field.code
        field.delete()
        messages.success(request, f"Field {code} deleted.")
    return redirect("processes:process_detail", pk=pk)


@admin_required
def process_link_subprocesses(request, pk):
    process = get_object_or_404(Process, pk=pk)
    if request.method == "POST":
        form = ProcessLinkSubProcessesForm(process, request.POST)
        if form.is_valid():
            selected = form.cleaned_data["subprocesses"]
            ProcessSubProcessLink.objects.filter(process=process).exclude(
                subprocess__in=selected
            ).delete()
            existing = set(
                ProcessSubProcessLink.objects.filter(process=process).values_list(
                    "subprocess_id", flat=True
                )
            )
            for i, sp in enumerate(selected):
                if sp.pk not in existing:
                    ProcessSubProcessLink.objects.create(
                        process=process, subprocess=sp, sort_order=i * 10
                    )
            messages.success(request, "Linked sub processes updated.")
            return redirect("processes:process_detail", pk=pk)
    else:
        form = ProcessLinkSubProcessesForm(process)
    return render(
        request,
        "processes/link_subprocesses.html",
        {"form": form, "process": process},
    )


@login_required
def subprocess_list(request):
    qs = SubProcess.objects.select_related("plant").order_by("code")
    return _master_list(
        request,
        qs,
        search_fields=("code", "name", "description", "plant__code", "plant__name"),
        panel_partial="processes/partials/subprocess_table_panel.html",
        full_template="processes/subprocess_list.html",
        context_list_key="items",
    )


@admin_required
def subprocess_create(request):
    if request.method == "POST":
        form = SubProcessForm(request.POST)
        formset = SubProcessFieldFormSet(request.POST)
        if form.is_valid() and formset.is_valid() and apply_formula_field_validation(form, formset):
            obj = form.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f"Sub process {obj.code} created.")
            return redirect("processes:subprocess_detail", pk=obj.pk)
    else:
        form = SubProcessForm(initial={"is_active": True, "result_formula": "0"})
        formset = SubProcessFieldFormSet()
    return render(
        request,
        "processes/subprocess_form.html",
        {"form": form, "formset": formset, "title": "Add Sub Process"},
    )


@login_required
def subprocess_detail(request, pk):
    obj = get_object_or_404(
        SubProcess.objects.select_related("plant").prefetch_related("fields", "processes"),
        pk=pk,
    )
    return render(request, "processes/subprocess_detail.html", {"subprocess": obj})


@admin_required
def subprocess_edit(request, pk):
    obj = get_object_or_404(SubProcess, pk=pk)
    if request.method == "POST":
        form = SubProcessForm(request.POST, instance=obj)
        formset = SubProcessFieldFormSet(request.POST, instance=obj)
        if form.is_valid() and formset.is_valid() and apply_formula_field_validation(form, formset):
            form.save()
            formset.save()
            messages.success(request, f"Sub process {obj.code} updated.")
            return redirect("processes:subprocess_detail", pk=pk)
    else:
        form = SubProcessForm(instance=obj)
        formset = SubProcessFieldFormSet(instance=obj)
    return render(
        request,
        "processes/subprocess_form.html",
        {"form": form, "formset": formset, "title": "Edit Sub Process", "subprocess": obj},
    )


@admin_required
def subprocess_soft_delete(request, pk):
    obj = get_object_or_404(SubProcess, pk=pk)
    if request.method == "POST":
        if obj.is_active:
            obj.is_active = False
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Sub process {obj.code} set to Inactive.")
        else:
            messages.info(request, f"Sub process {obj.code} is already inactive.")
    return redirect("processes:subprocess_list")


@admin_required
def subprocess_restore(request, pk):
    obj = get_object_or_404(SubProcess, pk=pk)
    if request.method == "POST":
        if not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Sub process {obj.code} restored (Active).")
        else:
            messages.info(request, f"Sub process {obj.code} is already active.")
    return redirect("processes:subprocess_list")


@admin_required
def subprocess_delete(request, pk):
    obj = get_object_or_404(SubProcess, pk=pk)
    if request.method == "POST":
        code = obj.code
        obj.delete()
        messages.success(request, f"Sub process {code} permanently deleted.")
        return redirect("processes:subprocess_list")
    return redirect("processes:subprocess_detail", pk=pk)


@admin_required
def subprocess_field_add(request, pk):
    subprocess = get_object_or_404(SubProcess, pk=pk)
    if request.method == "POST":
        form = SubProcessFieldForm(request.POST)
        if form.is_valid():
            field = form.save(commit=False)
            field.subprocess = subprocess
            field.save()
            messages.success(request, f"Field {field.code} added.")
            return redirect("processes:subprocess_detail", pk=pk)
    else:
        form = SubProcessFieldForm()
    return render(
        request,
        "processes/field_form.html",
        {
            "form": form,
            "title": "Add Sub Process Field",
            "back_url": reverse("processes:subprocess_detail", args=[pk]),
        },
    )


@admin_required
def subprocess_field_edit(request, pk, field_pk):
    subprocess = get_object_or_404(SubProcess, pk=pk)
    field = get_object_or_404(SubProcessField, pk=field_pk, subprocess=subprocess)
    if request.method == "POST":
        form = SubProcessFieldForm(request.POST, instance=field)
        if form.is_valid():
            form.save()
            messages.success(request, f"Field {field.code} updated.")
            return redirect("processes:subprocess_detail", pk=pk)
    else:
        form = SubProcessFieldForm(instance=field)
    return render(
        request,
        "processes/field_form.html",
        {
            "form": form,
            "title": "Edit Sub Process Field",
            "back_url": reverse("processes:subprocess_detail", args=[pk]),
        },
    )


@admin_required
def subprocess_field_delete(request, pk, field_pk):
    subprocess = get_object_or_404(SubProcess, pk=pk)
    field = get_object_or_404(SubProcessField, pk=field_pk, subprocess=subprocess)
    if request.method == "POST":
        code = field.code
        field.delete()
        messages.success(request, f"Field {code} deleted.")
    return redirect("processes:subprocess_detail", pk=pk)


@login_required
def quote_add_process(request, quote_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    if not quote.is_editable:
        messages.error(request, "Issued quotes are locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)
    wizard_mode = _in_quote_wizard(request)
    if request.method == "POST":
        form = QuoteAddProcessForm(quote, request.POST)
        if form.is_valid():
            process = form.cleaned_data["process"]
            if process.use_material_properties and not form.cleaned_data.get("material"):
                messages.error(request, "This process requires a material selection.")
                return render(
                    request,
                    "processes/quote_add_process.html",
                    {"quote": quote, "form": form, "wizard_mode": wizard_mode},
                )
            if process.use_machine_properties and not form.cleaned_data.get("machine"):
                messages.error(request, "This process requires a machine selection.")
                return render(
                    request,
                    "processes/quote_add_process.html",
                    {"quote": quote, "form": form, "wizard_mode": wizard_mode},
                )
            if process.use_labor_properties and not form.cleaned_data.get("labor_role"):
                messages.error(request, "This process requires a labor role selection.")
                return render(
                    request,
                    "processes/quote_add_process.html",
                    {"quote": quote, "form": form, "wizard_mode": wizard_mode},
                )
            qp = QuoteProcess.objects.create(
                quote=quote,
                process=process,
                material=form.cleaned_data.get("material"),
                machine=form.cleaned_data.get("machine"),
                labor_role=form.cleaned_data.get("labor_role"),
                notes=form.cleaned_data.get("notes") or "",
                sort_order=quote.quote_processes.count() * 10,
            )
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Process {process.code} added. Enter field values.")
            url = reverse(
                "processes:quote_process_fields",
                kwargs={"quote_pk": quote_pk, "qp_pk": qp.pk},
            )
            return redirect(url + _wizard_qs(request))
    else:
        form = QuoteAddProcessForm(quote)
    return render(
        request,
        "processes/quote_add_process.html",
        {"quote": quote, "form": form, "wizard_mode": wizard_mode},
    )


@login_required
def quote_process_fields(request, quote_pk, qp_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    qp = get_object_or_404(
        QuoteProcess.objects.select_related("process", "material"),
        pk=qp_pk,
        quote=quote,
    )
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)

    wizard_mode = _in_quote_wizard(request)
    fields = list(qp.process.fields.all())
    initial = {f"fld_{fv.field_code}": fv.value for fv in qp.field_values.all()}
    for f in fields:
        key = f"fld_{f.code}"
        if key not in initial and f.default_value != "":
            initial[key] = f.default_value

    if request.method == "POST":
        form = build_dynamic_field_form(fields, data=request.POST, prefix="fld")
        if form.is_valid():
            for code, value in form.values_by_code().items():
                QuoteProcessFieldValue.objects.update_or_create(
                    quote_process=qp, field_code=code, defaults={"value": value}
                )
            try:
                calculate_quote_process(qp)
            except Exception as exc:
                messages.error(request, f"Could not evaluate formula: {exc}")
                url = reverse(
                    "processes:quote_process_fields",
                    kwargs={"quote_pk": quote_pk, "qp_pk": qp.pk},
                )
                return redirect(url + _wizard_qs(request))
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, "Process field values saved.")
            return _redirect_quote_home(request, quote_pk)
    else:
        form = build_dynamic_field_form(fields, initial=initial, prefix="fld")

    return render(
        request,
        "processes/quote_process_fields.html",
        {"quote": quote, "qp": qp, "form": form, "wizard_mode": wizard_mode},
    )


@login_required
def quote_process_remove(request, quote_pk, qp_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    qp = get_object_or_404(QuoteProcess, pk=qp_pk, quote=quote)
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)
    if request.method == "POST":
        code = qp.process.code
        qp.delete()
        quote.status = Quote.Status.DRAFT
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Process {code} removed from quote.")
    return _redirect_quote_home(request, quote_pk)


@login_required
def quote_add_subprocess(request, quote_pk, qp_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    qp = get_object_or_404(QuoteProcess.objects.select_related("process"), pk=qp_pk, quote=quote)
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)
    wizard_mode = _in_quote_wizard(request)
    if request.method == "POST":
        form = QuoteAddSubProcessForm(qp, request.POST)
        if form.is_valid():
            sp = form.cleaned_data["subprocess"]
            qs = QuoteSubProcess.objects.create(
                quote_process=qp,
                subprocess=sp,
                notes=form.cleaned_data.get("notes") or "",
                sort_order=qp.subprocesses.count() * 10,
            )
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Sub process {sp.code} added.")
            url = reverse(
                "processes:quote_subprocess_fields",
                kwargs={"quote_pk": quote_pk, "qp_pk": qp.pk, "qs_pk": qs.pk},
            )
            return redirect(url + _wizard_qs(request))
    else:
        form = QuoteAddSubProcessForm(qp)
    return render(
        request,
        "processes/quote_add_subprocess.html",
        {"quote": quote, "qp": qp, "form": form, "wizard_mode": wizard_mode},
    )


@login_required
def quote_subprocess_fields(request, quote_pk, qp_pk, qs_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    qp = get_object_or_404(QuoteProcess, pk=qp_pk, quote=quote)
    qs = get_object_or_404(
        QuoteSubProcess.objects.select_related("subprocess"),
        pk=qs_pk,
        quote_process=qp,
    )
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)

    wizard_mode = _in_quote_wizard(request)
    fields = list(qs.subprocess.fields.all())
    initial = {f"fld_{fv.field_code}": fv.value for fv in qs.field_values.all()}
    for f in fields:
        key = f"fld_{f.code}"
        if key not in initial and f.default_value != "":
            initial[key] = f.default_value

    if request.method == "POST":
        form = build_dynamic_field_form(fields, data=request.POST, prefix="fld")
        if form.is_valid():
            for code, value in form.values_by_code().items():
                QuoteSubProcessFieldValue.objects.update_or_create(
                    quote_subprocess=qs, field_code=code, defaults={"value": value}
                )
            try:
                calculate_quote_process(qp)
            except Exception as exc:
                messages.error(request, f"Could not evaluate formula: {exc}")
                url = reverse(
                    "processes:quote_subprocess_fields",
                    kwargs={"quote_pk": quote_pk, "qp_pk": qp.pk, "qs_pk": qs.pk},
                )
                return redirect(url + _wizard_qs(request))
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, "Sub process field values saved.")
            return _redirect_quote_home(request, quote_pk)
    else:
        form = build_dynamic_field_form(fields, initial=initial, prefix="fld")

    return render(
        request,
        "processes/quote_subprocess_fields.html",
        {"quote": quote, "qp": qp, "qs": qs, "form": form, "wizard_mode": wizard_mode},
    )


@login_required
def quote_subprocess_remove(request, quote_pk, qp_pk, qs_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    qp = get_object_or_404(QuoteProcess, pk=qp_pk, quote=quote)
    qs = get_object_or_404(QuoteSubProcess, pk=qs_pk, quote_process=qp)
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)
    if request.method == "POST":
        code = qs.subprocess.code
        qs.delete()
        try:
            calculate_quote_process(qp)
        except Exception:
            pass
        quote.status = Quote.Status.DRAFT
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Sub process {code} removed.")
    return _redirect_quote_home(request, quote_pk)
