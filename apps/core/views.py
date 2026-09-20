from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.catalog.models import LaborRole, Machine, Material
from apps.processes.models import Process, SubProcess
from apps.quotes.models import Customer, Quote


def _greeting_name(user):
    raw = (user.first_name or user.get_username() or "there").strip()
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    return raw[:1].upper() + raw[1:] if raw else "there"


def _time_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


@login_required
def dashboard(request):
    quotes = Quote.objects.all()
    recent_quotes = (
        Quote.objects.select_related("customer", "plant")
        .order_by("-created_at", "-id")[:8]
    )

    ctx = {
        "greeting": _time_greeting(),
        "greeting_name": _greeting_name(request.user),
        "company_name": getattr(settings, "COMPANY_NAME", None) or "Prasad Manufacturing",
        "draft_count": quotes.filter(status=Quote.Status.DRAFT).count(),
        "calculated_count": quotes.filter(status=Quote.Status.CALCULATED).count(),
        "issued_count": quotes.filter(status=Quote.Status.ISSUED).count(),
        "material_count": Material.objects.filter(is_active=True).count(),
        "machine_count": Machine.objects.filter(is_active=True).count(),
        "labor_count": LaborRole.objects.filter(is_active=True).count(),
        "process_count": Process.objects.filter(is_active=True).count(),
        "subprocess_count": SubProcess.objects.filter(is_active=True).count(),
        "client_count": Customer.objects.filter(is_active=True).count(),
        "recent_quotes": recent_quotes,
    }
    return render(request, "core/dashboard.html", ctx)
