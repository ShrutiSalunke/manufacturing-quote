from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.catalog.models import LaborRole, Machine, Material
from apps.processes.models import Process, SubProcess
from apps.quotes.models import Quote


@login_required
def dashboard(request):
    ctx = {
        "material_count": Material.objects.filter(is_active=True).count(),
        "machine_count": Machine.objects.filter(is_active=True).count(),
        "labor_count": LaborRole.objects.filter(is_active=True).count(),
        "process_count": Process.objects.filter(is_active=True).count(),
        "subprocess_count": SubProcess.objects.filter(is_active=True).count(),
        "quote_count": Quote.objects.count(),
    }
    return render(request, "core/dashboard.html", ctx)
