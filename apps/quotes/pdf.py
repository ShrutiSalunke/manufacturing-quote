"""PDF generation for customer-facing quotes."""
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from apps.core.logging_utils import log_event
from apps.quotes.models import QuoteDocument


def generate_quote_pdf(quote, *, request=None, user=None) -> QuoteDocument:
    try:
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
        context = {
            "quote": quote,
            "company_name": getattr(settings, "COMPANY_NAME", "Manufacturing"),
            "lines": lines,
            "totals": data.get("totals", {}),
            "customer": quote.customer,
            "plant": quote.plant,
        }
        html = render_to_string("quotes/pdf_quote.html", context)
        buf = BytesIO()
        result = pisa.CreatePDF(html, dest=buf)
        if result.err:
            raise RuntimeError("xhtml2pdf reported errors while generating PDF")
        pdf_bytes = buf.getvalue()
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
