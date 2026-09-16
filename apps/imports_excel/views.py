import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.imports_excel.models import ImportJob
from apps.imports_excel.services import generate_template_workbook, import_workbook


@login_required
def imports_hub(request):
    jobs = ImportJob.objects.select_related("created_by").prefetch_related("row_errors")[:20]
    cards = [
        {"type": ImportJob.EntityType.MATERIAL, "title": "Materials", "desc": "Master material prices & density"},
        {"type": ImportJob.EntityType.MACHINE, "title": "Machines", "desc": "Work centers & hourly rates"},
        {"type": ImportJob.EntityType.LABOR, "title": "Labor Roles", "desc": "Labor rates by role"},
        {
            "type": ImportJob.EntityType.QUOTE_INPUT,
            "title": "Quote Line Inputs",
            "desc": "Bulk parameter values for quote lines",
        },
    ]
    return render(request, "imports_excel/hub.html", {"cards": cards, "jobs": jobs})


@login_required
def download_template(request, entity_type):
    if entity_type not in ImportJob.EntityType.values:
        messages.error(request, "Unknown template type.")
        return redirect("imports_excel:hub")
    content = generate_template_workbook(entity_type)
    filename = {
        ImportJob.EntityType.MATERIAL: "materials_template.xlsx",
        ImportJob.EntityType.MACHINE: "machines_template.xlsx",
        ImportJob.EntityType.LABOR: "labor_template.xlsx",
        ImportJob.EntityType.QUOTE_INPUT: "quote_inputs_template.xlsx",
    }[entity_type]
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def upload_import(request, entity_type):
    if entity_type not in ImportJob.EntityType.values:
        messages.error(request, "Unknown import type.")
        return redirect("imports_excel:hub")
    if request.method != "POST":
        return redirect("imports_excel:hub")
    uploaded = request.FILES.get("file")
    if not uploaded:
        messages.error(request, "Please choose an Excel file.")
        return redirect("imports_excel:hub")
    job = ImportJob.objects.create(
        entity_type=entity_type,
        uploaded_file=uploaded,
        created_by=request.user,
        correlation_id=getattr(request, "correlation_id", uuid.uuid4()),
    )
    try:
        import_workbook(job, request=request)
        if job.status == ImportJob.Status.SUCCESS:
            messages.success(request, f"Import complete: {job.row_success} rows.")
        elif job.status == ImportJob.Status.PARTIAL:
            messages.warning(
                request,
                f"Partial import: {job.row_success} ok, {job.row_failed} failed. "
                f"Correlation ID: {job.correlation_id}",
            )
        else:
            messages.error(
                request,
                f"Import failed: {job.error_summary}. Correlation ID: {job.correlation_id}",
            )
    except Exception as exc:
        messages.error(
            request,
            f"Import failed: {exc}. Correlation ID: {job.correlation_id}",
        )
    return redirect("imports_excel:job_detail", pk=job.pk)


@login_required
def job_detail(request, pk):
    job = get_object_or_404(ImportJob.objects.prefetch_related("row_errors"), pk=pk)
    return render(request, "imports_excel/job_detail.html", {"job": job})
