"""PDF generation for customer-facing quotes."""
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from apps.core.logging_utils import log_event
from apps.quotes.models import QuoteDocument


def build_quote_pdf_context(quote) -> dict:
    """Shared context for PDF file generation and on-screen preview."""
    calculation = getattr(quote, "calculation", None)
    data = calculation.data if calculation else {}
    lines = []
    for line in quote.lines.all():
        snap = line.snapshot or {}
        totals = snap.get("totals", {})
        qty = float(line.quantity)
        unit = totals.get("unit_selling_price", 0)
        amount = totals.get("selling_price", 0)
        lines.append(
            {
                "description": line.description,
                "quantity": qty,
                "unit_price": unit,
                "amount": amount,
            }
        )
    # One select/prefetch for all processes; avoid per-row .exists() queries.
    for qp in quote.quote_processes.select_related("process").prefetch_related(
        "subprocesses__subprocess"
    ):
        amount = float(qp.computed_total or 0)
        desc = f"{qp.process.code} — {qp.process.name}"
        sub_codes = [qs.subprocess.code for qs in qp.subprocesses.all()]
        if sub_codes:
            desc = f"{desc} (incl. {', '.join(sub_codes)})"
        lines.append(
            {
                "description": desc,
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
            }
        )
    totals = data.get("totals", {})
    if totals.get("combined_selling") is not None:
        display_totals = {
            **totals,
            "selling_price": totals.get("combined_selling", totals.get("selling_price", 0)),
        }
    else:
        display_totals = totals
    return {
        "quote": quote,
        "company_name": getattr(settings, "COMPANY_NAME", "Manufacturing"),
        "lines": lines,
        "totals": display_totals,
        "customer": quote.customer,
        "plant": quote.plant,
    }


def render_quote_pdf_html(quote) -> str:
    return render_to_string("quotes/pdf_quote.html", build_quote_pdf_context(quote))


def render_quote_pdf_bytes(quote) -> bytes:
    html = render_quote_pdf_html(quote)
    buf = BytesIO()
    result = pisa.CreatePDF(html, dest=buf)
    if result.err:
        raise RuntimeError("xhtml2pdf reported errors while generating PDF")
    return buf.getvalue()


def generate_quote_pdf(quote, *, request=None, user=None) -> QuoteDocument:
    try:
        pdf_bytes = render_quote_pdf_bytes(quote)
        filename = f"{quote.number}_v{quote.version}.pdf"
        doc = QuoteDocument(quote=quote)
        doc.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        doc.save()
        doc.file_hash = doc.compute_hash()
        doc.save(update_fields=["file_hash"])
        return doc
    except Exception as exc:
        entry = log_event(
            "ERROR",
            "quotes",
            "PDF",
            f"PDF generation failed for {quote.number}: {exc}",
            request=request,
            user=user,
            exc=exc,
            context={"quote_id": quote.pk, "quote_number": quote.number},
        )
        exc.correlation_id = entry.correlation_id if entry else None
        raise
