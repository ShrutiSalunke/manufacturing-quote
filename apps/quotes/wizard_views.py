"""
Multi-step New Quote wizard.

Navigation is driven by apps.quotes.wizard.QUOTE_WIZARD_STEPS so Machine / Labor
(or other) steps can be enabled later without rewriting the shell.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.costing.engine import FormulaError
from apps.costing.services import calculate_quote

from apps.processes.models import QuoteProcess
from apps.catalog.models import Material
from .forms import WIZARD_CLIENT_FIELDS, WizardQuoteDetailsForm
from .models import Customer, Quote, QuoteCalculationSnapshot
from .pdf import generate_quote_pdf, render_quote_pdf_bytes, render_quote_pdf_html
from . import wizard_process
from . import weight_calculator as weight_calc
from .wizard import (
    adjacent_step,
    enabled_steps,
    get_step,
    wizard_progress,
)


def _wizard_context(step_id, quote=None, **extra):
    step = get_step(step_id)
    if not step or not step.enabled:
        raise Http404("Unknown wizard step")
    ctx = {
        "quote": quote,
        "current_step": step,
        "wizard_steps": wizard_progress(step_id),
        "prev_step": adjacent_step(step_id, direction=-1),
        "next_step": adjacent_step(step_id, direction=1),
        "enabled_step_ids": [s.id for s in enabled_steps()],
    }
    ctx.update(extra)
    return ctx


def _load_quote(quote_pk):
    return get_object_or_404(
        Quote.objects.select_related(
            "customer", "plant", "calculation", "weight_material"
        ).prefetch_related(
            "quote_processes__process",
            "quote_processes__material",
            "quote_processes__field_values",
            "quote_processes__subprocesses__subprocess",
            "quote_processes__subprocesses__field_values",
        ),
        pk=quote_pk,
    )


def _step_url(step_id, quote=None):
    if quote is None:
        return reverse("quotes:wizard_step_new", kwargs={"step_id": step_id})
    return reverse(
        "quotes:wizard_step",
        kwargs={"quote_pk": quote.pk, "step_id": step_id},
    )


def _redirect_to_step(step_id, quote=None):
    return redirect(_step_url(step_id, quote))


@login_required
def wizard_start(request):
    """Entry point — always begins at the first enabled step."""
    first = enabled_steps()[0]
    return _redirect_to_step(first.id)


@login_required
def quote_create(request):
    """Keep URL name; send New Quote into the wizard."""
    return wizard_start(request)


@login_required
def wizard_step_new(request, step_id):
    """Steps that do not yet have a quote (details only today)."""
    step = get_step(step_id)
    if not step or not step.enabled:
        raise Http404("Unknown wizard step")
    if step.requires_quote:
        messages.info(request, "Start with quote details first.")
        return wizard_start(request)
    return _dispatch_step(request, step_id, quote=None)


@login_required
def wizard_step(request, quote_pk, step_id):
    step = get_step(step_id)
    if not step or not step.enabled:
        raise Http404("Unknown wizard step")
    quote = _load_quote(quote_pk)
    if not step.requires_quote:
        # Editing details for an existing draft still uses the quote-scoped URL.
        pass
    return _dispatch_step(request, step_id, quote=quote)


def _dispatch_step(request, step_id, quote):
    handlers = {
        "details": _step_details,
        "weight": _step_weight,
        "processes": _step_processes,
        "preview": _step_preview,
        # Future: "machines": _step_machines, "labor": _step_labor,
    }
    handler = handlers.get(step_id)
    if handler is None:
        messages.warning(
            request,
            f"Step “{step_id}” is registered but not implemented yet.",
        )
        return wizard_start(request)
    return handler(request, quote)


def _step_details(request, quote):
    instance = quote
    if request.method == "POST":
        form = WizardQuoteDetailsForm(request.POST, quote=instance)
        if form.is_valid():
            try:
                if instance is not None and instance.status == Quote.Status.ISSUED:
                    messages.error(request, "Issued quotes are locked.")
                    return _redirect_to_step("details", quote)
                created_new_client = form.cleaned_data.get("customer") is None
                saved = form.save_quote(user=request.user, quote=instance)
            except Exception as exc:
                messages.error(request, f"Could not save quote: {exc}")
                return render(
                    request,
                    "quotes/wizard/step_details.html",
                    _wizard_context(
                        "details",
                        quote=quote,
                        qform=form,
                        page_title="New Quote" if quote is None else f"Edit {quote.number}",
                        client_locked=bool(form.data.get("customer_id")),
                        client_suggest_url=reverse("quotes:client_suggest"),
                        wizard_client_fields=list(WIZARD_CLIENT_FIELDS),
                    ),
                )
            if created_new_client:
                messages.success(
                    request,
                    f"Client {saved.customer.code} created and quote {saved.number} saved.",
                )
            else:
                messages.success(
                    request,
                    f"Quote {saved.number} saved."
                    if instance is None
                    else "Quote details updated.",
                )
            nxt = adjacent_step("details", direction=1)
            if nxt:
                return _redirect_to_step(nxt.id, saved)
            return redirect("quotes:quote_detail", pk=saved.pk)
    else:
        form = WizardQuoteDetailsForm(quote=instance)

    client_locked = False
    if form.is_bound:
        client_locked = bool(form.data.get("customer_id"))
    elif quote and quote.customer_id:
        client_locked = True

    title = "New Quote" if quote is None else f"Edit {quote.number}"
    return render(
        request,
        "quotes/wizard/step_details.html",
        _wizard_context(
            "details",
            quote=quote,
            qform=form,
            page_title=title,
            client_locked=client_locked,
            client_suggest_url=reverse("quotes:client_suggest"),
            wizard_client_fields=list(WIZARD_CLIENT_FIELDS),
        ),
    )


@login_required
def client_suggest(request):
    """JSON typeahead for wizard client code / company fields."""
    q = (request.GET.get("q") or "").strip()
    field = (request.GET.get("field") or "").strip().lower()
    qs = Customer.objects.filter(is_active=True).order_by("code")
    if q:
        if field == "code":
            qs = qs.filter(code__icontains=q)
        elif field == "company":
            qs = qs.filter(Q(company__icontains=q) | Q(name__icontains=q))
        else:
            qs = qs.filter(
                Q(code__icontains=q)
                | Q(name__icontains=q)
                | Q(company__icontains=q)
            )
    results = []
    for c in qs[:12]:
        results.append(
            {
                "id": c.pk,
                "label": str(c),
                "code": c.code,
                "company": c.company,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "gstin": c.gstin,
                "address_line1": c.address_line1,
                "address_line2": c.address_line2,
                "city": c.city,
                "state": c.state,
                "postal_code": c.postal_code,
                "country": c.country or "India",
            }
        )
    return JsonResponse({"results": results})


def _metal_options_for_quote(quote):
    """Active Materials master rows for the quote plant."""
    options = []
    for m in Material.objects.filter(plant=quote.plant, is_active=True).order_by("code"):
        dens = (
            float(m.density)
            if m.density is not None
            else weight_calc.resolve_density(None, m.name, None)
        )
        options.append(
            {
                "id": m.pk,
                "label": f"{m.code} — {m.name}",
                "density": dens,
                "unit_price": float(m.unit_price or 0),
            }
        )
    return options


def _resolve_weight_material(quote, material_id):
    if not material_id:
        raise ValueError("Select a material from Materials master.")
    return get_object_or_404(
        Material, pk=int(material_id), plant=quote.plant, is_active=True
    )


def _step_weight(request, quote):
    if quote is None:
        return wizard_start(request)
    if not quote.is_editable:
        messages.error(request, "Issued quotes are locked.")
        return redirect("quotes:quote_detail", pk=quote.pk)

    if request.method == "POST":
        action = request.POST.get("wizard_action") or "next"
        if action == "back":
            prev = adjacent_step("weight", direction=-1)
            if prev:
                return _redirect_to_step(prev.id, quote)
            return _redirect_to_step("details", quote)

        if action in ("save_weight", "next", "calculate"):
            shape_id = (request.POST.get("shape_id") or "").strip()
            if not shape_id and action == "next":
                # Allow skipping weight calculator
                nxt = adjacent_step("weight", direction=1)
                if nxt:
                    return _redirect_to_step(nxt.id, quote)
                return redirect("quotes:quote_detail", pk=quote.pk)

            try:
                material_id = (request.POST.get("material_id") or "").strip()
                material = _resolve_weight_material(quote, material_id)
                density = weight_calc.resolve_density(
                    material.density,
                    material.name,
                    request.POST.get("density"),
                )

                # Collect dimensions / units from POST
                shape = weight_calc.SHAPE_BY_ID.get(shape_id)
                if not shape:
                    raise ValueError("Select a raw material shape.")
                dimensions = {}
                units = {}
                for f in shape["fields"]:
                    key = f["key"]
                    dimensions[key] = request.POST.get(f"dim_{key}", "")
                    units[key] = request.POST.get(f"unit_{key}", "mm")

                mode = request.POST.get("mode") or "by_length"
                pieces = request.POST.get("pieces") or 1
                price = request.POST.get("price_per_kg") or 0
                target_weight = request.POST.get("target_weight_kg") or None

                result = weight_calc.calculate(
                    shape_id=shape_id,
                    density=density,
                    mode=mode,
                    pieces=pieces,
                    price_per_kg=price,
                    dimensions=dimensions,
                    units=units,
                    target_weight_kg=float(target_weight) if target_weight not in (None, "") else None,
                )

                quote.weight_shape = shape_id
                quote.weight_material = material
                quote.weight_calc_data = {
                    "metal_label": material.name,
                    "material_id": material.pk,
                    "density": density,
                    "mode": mode,
                    "pieces": float(pieces),
                    "price_per_kg": float(price or 0),
                    "dimensions": dimensions,
                    "units": units,
                    "target_weight_kg": target_weight,
                    "result": result,
                }
                quote.save(
                    update_fields=[
                        "weight_shape",
                        "weight_material",
                        "weight_calc_data",
                        "updated_at",
                    ]
                )

                if action == "calculate":
                    return _redirect_to_step("weight", quote)

                if action == "save_weight":
                    messages.success(request, "Weight calculation saved.")
                    return _redirect_to_step("weight", quote)

                nxt = adjacent_step("weight", direction=1)
                if nxt:
                    return _redirect_to_step(nxt.id, quote)
                return redirect("quotes:quote_detail", pk=quote.pk)

            except ValueError as exc:
                messages.error(request, str(exc))
                return _render_weight_step(request, quote)
            except Exception as exc:
                messages.error(request, f"Could not calculate weight: {exc}")
                return _render_weight_step(request, quote)

        if action == "clear_weight":
            quote.weight_shape = ""
            quote.weight_material = None
            quote.weight_calc_data = {}
            quote.save(
                update_fields=[
                    "weight_shape",
                    "weight_material",
                    "weight_calc_data",
                    "updated_at",
                ]
            )
            messages.success(request, "Weight calculator cleared.")
            return _redirect_to_step("weight", quote)

        return _redirect_to_step("weight", quote)

    return _render_weight_step(request, quote)


def _render_weight_step(request, quote):
    quote = _load_quote(quote.pk)
    data = quote.weight_calc_data or {}
    return render(
        request,
        "quotes/wizard/step_weight.html",
        _wizard_context(
            "weight",
            quote=quote,
            page_title=f"Weight calculator — {quote.number}",
            shapes=weight_calc.SHAPES,
            metal_options=_metal_options_for_quote(quote),
            saved_shape=quote.weight_shape or data.get("result", {}).get("shape_id", ""),
            saved_data=data,
            preferred_material_id=quote.weight_material_id,
        ),
    )


def _step_processes(request, quote):
    if quote is None:
        return wizard_start(request)
    if not quote.is_editable:
        messages.error(request, "Issued quotes are locked.")
        return redirect("quotes:quote_detail", pk=quote.pk)

    if request.method == "POST":
        action = request.POST.get("wizard_action") or "next"
        if action == "back":
            prev = adjacent_step("processes", direction=-1)
            if prev:
                return _redirect_to_step(prev.id, quote)
            return _redirect_to_step("details", quote)

        if action == "remove_process":
            qp_id = request.POST.get("remove_qp_id") or request.POST.get("qp_id")
            if qp_id:
                qp = QuoteProcess.objects.filter(pk=qp_id, quote=quote).first()
                if qp:
                    code = qp.process.code
                    qp.delete()
                    quote.status = Quote.Status.DRAFT
                    quote.save(update_fields=["status", "updated_at"])
                    messages.success(request, f"Process {code} removed.")
            return _redirect_to_step("processes", quote)

        if action in ("save_processes", "next"):
            try:
                saved = wizard_process.save_wizard_process_blocks(quote, request.POST)
                if action == "save_processes":
                    messages.success(
                        request,
                        f"Saved {len(saved)} process(es) on this quote.",
                    )
                    return _redirect_to_step("processes", quote)
            except ValueError as exc:
                messages.error(request, str(exc))
                return _render_processes_step(request, quote)
            except Exception as exc:
                messages.error(request, f"Could not save processes: {exc}")
                return _render_processes_step(request, quote)

            if action == "next":
                quote = _load_quote(quote.pk)
                if not quote.quote_processes.exists():
                    messages.error(
                        request,
                        "Add at least one process before preview.",
                    )
                    return _render_processes_step(request, quote)
                nxt = adjacent_step("processes", direction=1)
                if nxt:
                    return _redirect_to_step(nxt.id, quote)
                return redirect("quotes:quote_detail", pk=quote.pk)

        return _redirect_to_step("processes", quote)

    return _render_processes_step(request, quote)


def _render_processes_step(request, quote, keep_post=False):
    quote = _load_quote(quote.pk)
    return render(
        request,
        "quotes/wizard/step_processes.html",
        _wizard_context(
            "processes",
            quote=quote,
            page_title=f"Processes — {quote.number}",
            process_options=wizard_process.available_processes(quote),
            existing_blocks=wizard_process.existing_blocks_payload(quote),
            process_schema_url=reverse(
                "quotes:wizard_process_schema", kwargs={"quote_pk": quote.pk}
            ),
            process_autofill_url=reverse(
                "quotes:wizard_process_autofill", kwargs={"quote_pk": quote.pk}
            ),
            preferred_material_id=quote.weight_material_id,
        ),
    )


@login_required
def wizard_process_schema(request, quote_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    process_id = request.GET.get("process_id")
    if not process_id:
        return JsonResponse({"error": "process_id required"}, status=400)
    try:
        data = wizard_process.process_schema(quote, int(process_id))
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse(data)


@login_required
def wizard_process_autofill(request, quote_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    process_id = request.GET.get("process_id")
    material_id = request.GET.get("material_id")
    if not process_id or not material_id:
        return JsonResponse({"error": "process_id and material_id required"}, status=400)
    try:
        data = wizard_process.material_autofill_values(
            quote, int(process_id), int(material_id)
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse(data)


@login_required
def wizard_process_instance(request, quote_pk, qp_pk):
    quote = get_object_or_404(Quote, pk=quote_pk)
    try:
        data = wizard_process.quote_process_payload(quote, qp_pk)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    return JsonResponse(data)


def _step_preview(request, quote):
    if quote is None:
        return wizard_start(request)

    if request.method == "POST":
        action = request.POST.get("wizard_action") or "refresh"
        if action == "back":
            prev = adjacent_step("preview", direction=-1)
            if prev:
                return _redirect_to_step(prev.id, quote)
            return _redirect_to_step("processes", quote)
        if action == "calculate":
            if not quote.is_editable:
                messages.error(request, "Issued quotes cannot be recalculated.")
            elif not quote.quote_processes.exists() and not quote.lines.exists():
                messages.error(request, "Add at least one process before calculating.")
            else:
                try:
                    calculate_quote(quote, request=request, user=request.user)
                    messages.success(request, "Quote calculated. Preview updated.")
                except FormulaError as exc:
                    cid = getattr(exc, "correlation_id", None) or getattr(
                        request, "correlation_id", ""
                    )
                    messages.error(
                        request,
                        f"Costing failed: {exc}. Correlation ID: {cid}.",
                    )
            return _redirect_to_step("preview", quote)
        if action == "download":
            return _download_preview_pdf(request, quote)
        if action == "finish":
            return redirect("quotes:quote_detail", pk=quote.pk)

    # Soft-calc on first visit when draft has processes but no calculation yet.
    has_calculation = False
    try:
        has_calculation = quote.calculation is not None
    except QuoteCalculationSnapshot.DoesNotExist:
        has_calculation = False
    if (
        quote.is_editable
        and quote.quote_processes.exists()
        and quote.status == Quote.Status.DRAFT
        and not has_calculation
    ):
        try:
            calculate_quote(quote, request=request, user=request.user)
            quote = _load_quote(quote.pk)
        except FormulaError:
            pass

    return render(
        request,
        "quotes/wizard/step_preview.html",
        _wizard_context(
            "preview",
            quote=quote,
            page_title=f"Preview — {quote.number}",
            preview_html_url=reverse(
                "quotes:wizard_preview_html", kwargs={"quote_pk": quote.pk}
            ),
            preview_pdf_url=reverse(
                "quotes:wizard_preview_pdf", kwargs={"quote_pk": quote.pk}
            ),
            can_download=quote.status
            in (Quote.Status.CALCULATED, Quote.Status.ISSUED),
        ),
    )


def _download_preview_pdf(request, quote):
    if quote.status not in (Quote.Status.CALCULATED, Quote.Status.ISSUED):
        if quote.is_editable and (
            quote.quote_processes.exists() or quote.lines.exists()
        ):
            try:
                calculate_quote(quote, request=request, user=request.user)
                quote.refresh_from_db()
            except FormulaError as exc:
                messages.error(request, f"Calculate before download: {exc}")
                return _redirect_to_step("preview", quote)
        else:
            messages.error(request, "Calculate the quote before generating a PDF.")
            return _redirect_to_step("preview", quote)
    try:
        doc = generate_quote_pdf(quote, request=request, user=request.user)
        return FileResponse(
            doc.pdf_file.open("rb"),
            as_attachment=True,
            filename=doc.pdf_file.name.split("/")[-1],
        )
    except Exception as exc:
        cid = getattr(exc, "correlation_id", None) or getattr(request, "correlation_id", "")
        messages.error(
            request,
            f"PDF generation failed: {exc}. Correlation ID: {cid}.",
        )
        return _redirect_to_step("preview", quote)


@login_required
@xframe_options_sameorigin
def wizard_preview_html(request, quote_pk):
    """HTML document matching the downloadable PDF (iframe-friendly)."""
    quote = _load_quote(quote_pk)
    html = render_quote_pdf_html(quote)
    return HttpResponse(html)


@login_required
@xframe_options_sameorigin
def wizard_preview_pdf(request, quote_pk):
    """Raw PDF bytes for embed/object preview (same bytes as download)."""
    quote = _load_quote(quote_pk)
    try:
        if quote.status == Quote.Status.DRAFT and quote.is_editable and (
            quote.quote_processes.exists() or quote.lines.exists()
        ):
            try:
                calculate_quote(quote, request=request, user=request.user)
                quote = _load_quote(quote_pk)
            except FormulaError:
                pass
        pdf_bytes = render_quote_pdf_bytes(quote)
    except Exception as exc:
        return HttpResponse(
            f"PDF preview unavailable: {exc}",
            status=500,
            content_type="text/plain",
        )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{quote.number}_preview.pdf"'
    return response
