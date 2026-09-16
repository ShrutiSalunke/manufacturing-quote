import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.costing.engine import FormulaError
from apps.costing.services import calculate_quote
from apps.templates_engine.models import ProductTemplate

from .forms import CustomerForm, QuoteForm, QuoteLineForm, QuoteLineParametersForm
from .models import Customer, Quote, QuoteDocument, QuoteLine, QuoteLineParameterValue
from .pdf import generate_quote_pdf


@login_required
def quote_list(request):
    quotes = Quote.objects.select_related("customer", "plant", "created_by").all()
    return render(request, "quotes/quote_list.html", {"quotes": quotes})


@login_required
def quote_create(request):
    if request.method == "POST":
        qform = QuoteForm(request.POST)
        cform = CustomerForm(request.POST)
        if qform.is_valid() and cform.is_valid():
            customer = cform.save()
            quote = qform.save(commit=False)
            quote.customer = customer
            quote.created_by = request.user
            quote.currency = quote.plant.currency
            quote.save()
            messages.success(request, f"Quote {quote.number} created.")
            return redirect("quotes:quote_detail", pk=quote.pk)
    else:
        qform = QuoteForm()
        cform = CustomerForm()
    return render(request, "quotes/quote_form.html", {"qform": qform, "cform": cform})


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(
        Quote.objects.select_related("customer", "plant", "calculation"),
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
    if not quote.lines.exists():
        messages.error(request, "Add at least one line before calculating.")
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
    messages.success(request, f"Created editable quote {new.number}.")
    return redirect("quotes:quote_detail", pk=new.pk)
