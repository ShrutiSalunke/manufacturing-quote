from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import admin_required
from apps.costing.engine import FormulaError
from apps.costing.services import calculate_quote
from apps.templates_engine.models import ProductTemplate

from .forms import CustomerForm, QuoteForm, QuoteLineForm, QuoteLineParametersForm
from .models import Customer, Quote, QuoteDocument, QuoteLine, QuoteLineParameterValue
from .pdf import generate_quote_pdf

CLIENT_PER_PAGE_CHOICES = (10, 15, 25, 50)
CLIENT_DEFAULT_PER_PAGE = 15


def _page_number_window(page_obj, adjacent=1):
    """Return page numbers with None placeholders for ellipsis."""
    current = page_obj.number
    total = page_obj.paginator.num_pages
    if total <= 7:
        return list(range(1, total + 1))
    pages = set([1, total, current])
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


@login_required
def client_list(request):
    qs = Customer.objects.all().order_by("-created_at", "-id")
    q = (request.GET.get("q") or "").strip()
    active = request.GET.get("active") or ""
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(company__icontains=q)
            | Q(name__icontains=q)
            | Q(email__icontains=q)
            | Q(gstin__icontains=q)
        )
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)

    try:
        per_page = int(request.GET.get("per_page") or CLIENT_DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = CLIENT_DEFAULT_PER_PAGE
    if per_page not in CLIENT_PER_PAGE_CHOICES:
        per_page = CLIENT_DEFAULT_PER_PAGE

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        "clients": page_obj.object_list,
        "q": q,
        "active": active,
        "per_page": per_page,
        "per_page_choices": CLIENT_PER_PAGE_CHOICES,
        "page_numbers": _page_number_window(page_obj),
    }
    template = (
        "quotes/partials/client_table_panel.html"
        if getattr(request, "htmx", False)
        else "quotes/client_list.html"
    )
    return render(request, template, context)


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Customer, pk=pk)
    quotes = client.quotes.select_related("plant").order_by("-created_at")[:20]
    return render(
        request,
        "quotes/client_detail.html",
        {"client": client, "quotes": quotes},
    )


@admin_required
def client_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            client = form.save()
            return render(
                request,
                "quotes/client_form.html",
                {
                    "form": CustomerForm(instance=client),
                    "title": "Add New Client",
                    "client": client,
                    "success_message": f"Client {client.code} created.",
                    "success_redirect": reverse("quotes:client_list"),
                },
            )
    else:
        form = CustomerForm(initial={"is_active": True, "country": "India"})
    return render(
        request,
        "quotes/client_form.html",
        {"form": form, "title": "Add New Client"},
    )


@admin_required
def client_edit(request, pk):
    client = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            return render(
                request,
                "quotes/client_form.html",
                {
                    "form": CustomerForm(instance=client),
                    "title": "Edit Client",
                    "client": client,
                    "success_message": f"Client {client.code} updated.",
                    "success_redirect": reverse("quotes:client_list"),
                },
            )
    else:
        form = CustomerForm(instance=client)
    return render(
        request,
        "quotes/client_form.html",
        {"form": form, "title": "Edit Client", "client": client},
    )


@admin_required
def client_soft_delete(request, pk):
    """Soft delete: mark client inactive. Row is kept for existing quotes."""
    client = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        if client.is_active:
            client.is_active = False
            client.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                f"Client {client.code} soft-deleted (set to Inactive). Existing quotes are unchanged.",
            )
        else:
            messages.info(request, f"Client {client.code} is already inactive.")
    return redirect("quotes:client_list")


@admin_required
def client_restore(request, pk):
    """Restore a soft-deleted client (set active again)."""
    client = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        if not client.is_active:
            client.is_active = True
            client.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"Client {client.code} restored (Active).")
        else:
            messages.info(request, f"Client {client.code} is already active.")
    return redirect("quotes:client_list")


@admin_required
def client_permanent_delete(request, pk):
    """Hard-delete client. Related quotes keep rows with customer set to NULL."""
    client = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        code = client.code
        client.delete()
        messages.success(
            request,
            f"Client {code} permanently deleted. Related quotes now have no client linked.",
        )
    return redirect("quotes:client_list")


@login_required
def quote_list(request):
    quotes = Quote.objects.select_related("customer", "plant", "created_by").all()
    return render(request, "quotes/quote_list.html", {"quotes": quotes})


@login_required
def quote_create(request):
    if request.method == "POST":
        qform = QuoteForm(request.POST)
        if qform.is_valid():
            quote = qform.save(commit=False)
            quote.created_by = request.user
            quote.currency = quote.plant.currency
            quote.save()
            messages.success(request, f"Quote {quote.number} created.")
            return redirect("quotes:quote_detail", pk=quote.pk)
    else:
        qform = QuoteForm()
    return render(request, "quotes/quote_form.html", {"qform": qform})


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(
        Quote.objects.select_related("customer", "plant", "calculation").prefetch_related(
            "quote_processes__process",
            "quote_processes__material",
            "quote_processes__field_values",
            "quote_processes__subprocesses__subprocess",
            "quote_processes__subprocesses__field_values",
            "lines__template",
            "lines__parameter_values",
        ),
        pk=pk,
    )
    return render(request, "quotes/quote_detail.html", {"quote": quote})


@login_required
def quote_add_line(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if not quote.is_editable:
        messages.error(request, "Issued quotes are locked. Create a new version to edit.")
        return redirect("quotes:quote_detail", pk=pk)
    if request.method == "POST":
        form = QuoteLineForm(request.POST, plant=quote.plant)
        if form.is_valid():
            line = form.save(commit=False)
            line.quote = quote
            if line.template.status != ProductTemplate.Status.PUBLISHED:
                messages.error(request, "Only published templates can be used.")
                return redirect("quotes:quote_add_line", pk=pk)
            line.save()
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status"])
            messages.success(request, "Line added. Enter parameters next.")
            return redirect("quotes:line_parameters", quote_pk=pk, line_pk=line.pk)
    else:
        form = QuoteLineForm(plant=quote.plant)
    return render(request, "quotes/add_line.html", {"quote": quote, "form": form})


@login_required
def line_parameters(request, quote_pk, line_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    line = get_object_or_404(QuoteLine.objects.select_related("template"), pk=line_pk, quote=quote)
    if not quote.is_editable:
        messages.error(request, "Quote is locked.")
        return redirect("quotes:quote_detail", pk=quote_pk)
    if request.method == "POST":
        form = QuoteLineParametersForm(line.template, request.POST)
        if form.is_valid():
            for code, value in form.parameter_values().items():
                QuoteLineParameterValue.objects.update_or_create(
                    line=line, parameter_code=code, defaults={"value": str(value)}
                )
            quote.status = Quote.Status.DRAFT
            quote.save(update_fields=["status"])
            messages.success(request, "Parameters saved.")
            return redirect("quotes:quote_detail", pk=quote_pk)
    else:
        initial = {f"param_{pv.parameter_code}": pv.value for pv in line.parameter_values.all()}
        form = QuoteLineParametersForm(line.template, initial=initial)
    return render(request, "quotes/line_parameters.html", {"quote": quote, "line": line, "form": form})


@login_required
def quote_calculate(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if not quote.is_editable:
        messages.error(request, "Issued quotes cannot be recalculated.")
        return redirect("quotes:quote_detail", pk=pk)
    if request.method != "POST":
        return redirect("quotes:quote_detail", pk=pk)
    if not quote.lines.exists() and not quote.quote_processes.exists():
        messages.error(request, "Add at least one process before calculating.")
        return redirect("quotes:quote_detail", pk=pk)
    try:
        calculate_quote(quote, request=request, user=request.user)
        messages.success(request, "Quote calculated successfully.")
    except FormulaError as exc:
        cid = getattr(exc, "correlation_id", None) or getattr(request, "correlation_id", "")
        messages.error(
            request,
            f"Costing failed: {exc}. Correlation ID: {cid} — search Error Logs with this ID.",
        )
    return redirect("quotes:quote_detail", pk=pk)


@login_required
def quote_pdf(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if quote.status not in (Quote.Status.CALCULATED, Quote.Status.ISSUED):
        messages.error(request, "Calculate the quote before generating a PDF.")
        return redirect("quotes:quote_detail", pk=pk)
    try:
        doc = generate_quote_pdf(quote, request=request, user=request.user)
        return FileResponse(doc.pdf_file.open("rb"), as_attachment=True, filename=doc.pdf_file.name.split("/")[-1])
    except Exception as exc:
        cid = getattr(exc, "correlation_id", None) or getattr(request, "correlation_id", "")
        messages.error(
            request,
            f"PDF generation failed: {exc}. Correlation ID: {cid} — search Error Logs with this ID.",
        )
        return redirect("quotes:quote_detail", pk=pk)


@login_required
def quote_issue(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if request.method == "POST":
        if quote.status != Quote.Status.CALCULATED:
            messages.error(request, "Only calculated quotes can be issued.")
        else:
            quote.status = Quote.Status.ISSUED
            quote.issued_at = timezone.now()
            quote.save(update_fields=["status", "issued_at", "updated_at"])
            messages.success(request, "Quote marked as Issued and locked.")
    return redirect("quotes:quote_detail", pk=pk)


@login_required
def quote_clone_version(request, pk):
    source = get_object_or_404(Quote, pk=pk)
    if request.method != "POST":
        return redirect("quotes:quote_detail", pk=pk)
    new = Quote.objects.create(
        number=f"{source.number}-V{source.version + 1}",
        version=source.version + 1,
        status=Quote.Status.DRAFT,
        plant=source.plant,
        customer=source.customer,
        currency=source.currency,
        valid_until=source.valid_until,
        notes=source.notes,
        created_by=request.user,
    )
    for line in source.lines.all():
        nl = QuoteLine.objects.create(
            quote=new,
            template=line.template,
            description=line.description,
            quantity=line.quantity,
            sort_order=line.sort_order,
        )
        for pv in line.parameter_values.all():
            QuoteLineParameterValue.objects.create(
                line=nl, parameter_code=pv.parameter_code, value=pv.value
            )
    # Clone process tree
    from apps.processes.models import (
        QuoteProcess,
        QuoteProcessFieldValue,
        QuoteSubProcess,
        QuoteSubProcessFieldValue,
    )

    for qp in source.quote_processes.all():
        nqp = QuoteProcess.objects.create(
            quote=new,
            process=qp.process,
            material=qp.material,
            sort_order=qp.sort_order,
            notes=qp.notes,
        )
        for fv in qp.field_values.all():
            QuoteProcessFieldValue.objects.create(
                quote_process=nqp, field_code=fv.field_code, value=fv.value
            )
        for qs in qp.subprocesses.all():
            nqs = QuoteSubProcess.objects.create(
                quote_process=nqp,
                subprocess=qs.subprocess,
                sort_order=qs.sort_order,
                notes=qs.notes,
            )
            for fv in qs.field_values.all():
                QuoteSubProcessFieldValue.objects.create(
                    quote_subprocess=nqs, field_code=fv.field_code, value=fv.value
                )
    messages.success(request, f"Created editable quote {new.number}.")
    return redirect("quotes:quote_detail", pk=new.pk)
