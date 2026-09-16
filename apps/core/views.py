from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.catalog.models import LaborRole, Machine, Material
from apps.quotes.models import Quote
from apps.templates_engine.models import ProductTemplate


@login_required
def dashboard(request):
    ctx = {
        "material_count": Material.objects.filter(is_active=True).count(),
        "machine_count": Machine.objects.filter(is_active=True).count(),
        "labor_count": LaborRole.objects.filter(is_active=True).count(),
        "template_count": ProductTemplate.objects.filter(status=ProductTemplate.Status.PUBLISHED).count(),
        "quote_count": Quote.objects.count(),
    }
    return render(request, "core/dashboard.html", ctx)
