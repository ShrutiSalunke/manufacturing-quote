from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import require_perm

from .models import SystemLog


@require_perm("error_logs", "view")
def log_list(request):
    qs = SystemLog.objects.select_related("user").all()
    level = request.GET.get("level", "").strip()
    event_type = request.GET.get("event_type", "").strip()
    q = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if level:
        qs = qs.filter(level=level)
    if event_type:
        qs = qs.filter(event_type=event_type)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q:
        qs = qs.filter(
            Q(message__icontains=q)
            | Q(traceback__icontains=q)
            | Q(correlation_id__icontains=q)
            | Q(source__icontains=q)
        )

    return render(
        request,
        "auditlog/log_list.html",
        {
            "logs": qs[:200],
            "levels": SystemLog.Level.choices,
            "event_types": SystemLog.EventType.choices,
            "filters": {
                "level": level,
                "event_type": event_type,
                "q": q,
                "date_from": date_from,
                "date_to": date_to,
            },
        },
    )


@require_perm("error_logs", "view")
def log_detail(request, pk):
    log = get_object_or_404(SystemLog.objects.select_related("user"), pk=pk)
    return render(request, "auditlog/log_detail.html", {"log": log})


@require_perm("error_logs", "purge")
def log_purge(request):
    if request.method == "POST":
        try:
            days = int(request.POST.get("days", "30"))
        except ValueError:
            days = 30
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = SystemLog.objects.filter(created_at__lt=cutoff).delete()
        messages.success(request, f"Deleted {deleted} log rows older than {days} days.")
    return redirect("auditlog:log_list")
