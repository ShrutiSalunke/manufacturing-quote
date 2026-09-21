"""Helpers for inline quote-wizard process step (schema + persist)."""
from __future__ import annotations

from django.shortcuts import get_object_or_404

from apps.catalog.models import LaborRole, Machine, Material
from apps.processes import labor_bridge, machine_bridge, material_bridge
from apps.processes.models import (
    Process,
    QuoteProcess,
    QuoteProcessFieldValue,
    QuoteSubProcess,
    QuoteSubProcessFieldValue,
)
from apps.processes.services import calculate_quote_process


def _serialize_field(f) -> dict:
    return {
        "code": f.code,
        "label": f.label,
        "data_type": f.data_type,
        "unit": f.unit or "",
        "default_value": f.default_value or "",
        "min_value": str(f.min_value) if f.min_value is not None else None,
        "max_value": str(f.max_value) if f.max_value is not None else None,
        "is_required": bool(f.is_required),
        "help_text": f.help_text or "",
        "material_property_key": f.material_property_key or "",
        "machine_property_key": getattr(f, "machine_property_key", "") or "",
        "labor_property_key": getattr(f, "labor_property_key", "") or "",
    }


def _plant_materials_payload(quote) -> list[dict]:
    return [
        {"id": m.pk, "label": f"{m.code} — {m.name}"}
        for m in Material.objects.filter(plant=quote.plant, is_active=True).order_by("code")
    ]


def _plant_machines_payload(quote) -> list[dict]:
    return [
        {"id": m.pk, "label": f"{m.code} — {m.name}"}
        for m in Machine.objects.filter(plant=quote.plant, is_active=True).order_by("code")
    ]


def _plant_labor_payload(quote) -> list[dict]:
    return [
        {"id": r.pk, "label": f"{r.code} — {r.name}"}
        for r in LaborRole.objects.filter(plant=quote.plant, is_active=True).order_by("code")
    ]


def _schema_from_process(
    process,
    materials_payload: list[dict] | None = None,
    machines_payload: list[dict] | None = None,
    labor_payload: list[dict] | None = None,
) -> dict:
    """Build process schema dict from an already-loaded Process (prefers prefetch cache)."""
    materials = list(materials_payload) if process.use_material_properties and materials_payload is not None else []
    machines = list(machines_payload) if process.use_machine_properties and machines_payload is not None else []
    labor_roles = list(labor_payload) if process.use_labor_properties and labor_payload is not None else []
    active_subs = sorted(
        (sp for sp in process.subprocesses.all() if sp.is_active),
        key=lambda sp: sp.code,
    )
    subs = [
        {
            "id": sp.pk,
            "code": sp.code,
            "name": sp.name,
            "result_unit": sp.result_unit,
            "fields": [_serialize_field(f) for f in sp.fields.all()],
        }
        for sp in active_subs
    ]
    return {
        "process": {
            "id": process.pk,
            "code": process.code,
            "name": process.name,
            "result_unit": process.result_unit,
            "use_material_properties": bool(process.use_material_properties),
            "use_machine_properties": bool(process.use_machine_properties),
            "use_labor_properties": bool(process.use_labor_properties),
        },
        "fields": [_serialize_field(f) for f in process.fields.all()],
        "materials": materials,
        "machines": machines,
        "labor_roles": labor_roles,
        "subprocesses": subs,
    }


def process_schema(
    quote,
    process_id: int,
    *,
    process=None,
    materials_payload: list[dict] | None = None,
    machines_payload: list[dict] | None = None,
    labor_payload: list[dict] | None = None,
) -> dict:
    if process is None:
        process = get_object_or_404(
            Process.objects.prefetch_related("fields", "subprocesses__fields"),
            pk=process_id,
            plant=quote.plant,
            is_active=True,
        )
    if process.use_material_properties and materials_payload is None:
        materials_payload = _plant_materials_payload(quote)
    if process.use_machine_properties and machines_payload is None:
        machines_payload = _plant_machines_payload(quote)
    if process.use_labor_properties and labor_payload is None:
        labor_payload = _plant_labor_payload(quote)
    return _schema_from_process(
        process, materials_payload, machines_payload, labor_payload
    )


def material_autofill_values(quote, process_id: int, material_id: int) -> dict:
    return catalog_autofill_values(quote, process_id, material_id=material_id)


def catalog_autofill_values(
    quote,
    process_id: int,
    *,
    material_id: int | None = None,
    machine_id: int | None = None,
    labor_id: int | None = None,
) -> dict:
    process = get_object_or_404(
        Process.objects.prefetch_related("fields", "subprocesses__fields"),
        pk=process_id,
        plant=quote.plant,
        is_active=True,
    )
    material = None
    machine = None
    labor = None
    if material_id:
        material = get_object_or_404(
            Material, pk=int(material_id), plant=quote.plant, is_active=True
        )
    if machine_id:
        machine = get_object_or_404(
            Machine, pk=int(machine_id), plant=quote.plant, is_active=True
        )
    if labor_id:
        labor = get_object_or_404(
            LaborRole, pk=int(labor_id), plant=quote.plant, is_active=True
        )

    process_vals: dict = {}
    for f in process.fields.all():
        if material and f.material_property_key:
            resolved = material_bridge.resolve_material_property(
                material, f.material_property_key
            )
            if resolved is not None and resolved != "":
                process_vals.setdefault(f.code, str(resolved))
        if machine and getattr(f, "machine_property_key", None):
            resolved = machine_bridge.resolve_machine_property(
                machine, f.machine_property_key
            )
            if resolved is not None and resolved != "":
                process_vals.setdefault(f.code, str(resolved))
        if labor and getattr(f, "labor_property_key", None):
            resolved = labor_bridge.resolve_labor_property(labor, f.labor_property_key)
            if resolved is not None and resolved != "":
                process_vals.setdefault(f.code, str(resolved))

    sub_vals: dict = {}
    for sp in process.subprocesses.all():
        if not sp.is_active:
            continue
        sp_map: dict = {}
        for f in sp.fields.all():
            if material and f.material_property_key:
                resolved = material_bridge.resolve_material_property(
                    material, f.material_property_key
                )
                if resolved is not None and resolved != "":
                    sp_map.setdefault(f.code, str(resolved))
            if machine and getattr(f, "machine_property_key", None):
                resolved = machine_bridge.resolve_machine_property(
                    machine, f.machine_property_key
                )
                if resolved is not None and resolved != "":
                    sp_map.setdefault(f.code, str(resolved))
            if labor and getattr(f, "labor_property_key", None):
                resolved = labor_bridge.resolve_labor_property(
                    labor, f.labor_property_key
                )
                if resolved is not None and resolved != "":
                    sp_map.setdefault(f.code, str(resolved))
        if sp_map:
            sub_vals[str(sp.pk)] = sp_map
    return {"process_fields": process_vals, "subprocess_fields": sub_vals}


def quote_process_payload(
    quote,
    qp_pk: int,
    *,
    qp=None,
    materials_payload: list[dict] | None = None,
    machines_payload: list[dict] | None = None,
    labor_payload: list[dict] | None = None,
) -> dict:
    if qp is None:
        qp = get_object_or_404(
            QuoteProcess.objects.select_related(
                "process", "material", "machine", "labor_role"
            ).prefetch_related(
                "field_values",
                "subprocesses__field_values",
                "subprocesses__subprocess",
                "process__fields",
                "process__subprocesses__fields",
            ),
            pk=qp_pk,
            quote=quote,
        )
    schema = process_schema(
        quote,
        qp.process_id,
        process=qp.process,
        materials_payload=materials_payload,
        machines_payload=machines_payload,
        labor_payload=labor_payload,
    )
    schema["qp_id"] = qp.pk
    schema["material_id"] = qp.material_id
    schema["machine_id"] = qp.machine_id
    schema["labor_id"] = qp.labor_role_id
    schema["values"] = {fv.field_code: fv.value for fv in qp.field_values.all()}
    subprocess_rows = list(qp.subprocesses.all())
    schema["selected_subprocess_ids"] = [qs.subprocess_id for qs in subprocess_rows]
    schema["subprocess_values"] = {
        str(qs.subprocess_id): {fv.field_code: fv.value for fv in qs.field_values.all()}
        for qs in subprocess_rows
    }
    return schema


def existing_blocks_payload(quote) -> list[dict]:
    """Serialize all quote processes for multi-block editor hydration."""
    materials_payload = _plant_materials_payload(quote)
    machines_payload = _plant_machines_payload(quote)
    labor_payload = _plant_labor_payload(quote)
    qps = quote.quote_processes.select_related(
        "process", "material", "machine", "labor_role"
    ).prefetch_related(
        "field_values",
        "subprocesses__field_values",
        "subprocesses__subprocess",
        "process__fields",
        "process__subprocesses__fields",
    )
    return [
        quote_process_payload(
            quote,
            qp.pk,
            qp=qp,
            materials_payload=materials_payload,
            machines_payload=machines_payload,
            labor_payload=labor_payload,
        )
        for qp in qps
    ]


def _read_field_values(post, field_defs, prefix: str) -> dict:
    out = {}
    for f in field_defs:
        key = f"{prefix}{f.code}"
        if f.data_type == "bool":
            out[f.code] = "1" if post.get(key) in ("on", "1", "true", "True") else "0"
        else:
            out[f.code] = (post.get(key) or "").strip()
            if f.is_required and out[f.code] == "":
                raise ValueError(f"{f.label} is required.")
    return out


def _resolve_optional_catalog(quote, process, post, prefix: str):
    material = None
    machine = None
    labor = None

    material_id = (post.get(f"{prefix}material_id") or "").strip()
    if process.use_material_properties:
        if not material_id:
            raise ValueError(f"Process {process.code} requires a material.")
        material = get_object_or_404(
            Material, pk=int(material_id), plant=quote.plant, is_active=True
        )
    elif material_id:
        material = get_object_or_404(
            Material, pk=int(material_id), plant=quote.plant, is_active=True
        )

    machine_id = (post.get(f"{prefix}machine_id") or "").strip()
    if process.use_machine_properties:
        if not machine_id:
            raise ValueError(f"Process {process.code} requires a machine.")
        machine = get_object_or_404(
            Machine, pk=int(machine_id), plant=quote.plant, is_active=True
        )
    elif machine_id:
        machine = get_object_or_404(
            Machine, pk=int(machine_id), plant=quote.plant, is_active=True
        )

    labor_id = (post.get(f"{prefix}labor_id") or "").strip()
    if process.use_labor_properties:
        if not labor_id:
            raise ValueError(f"Process {process.code} requires a labor role.")
        labor = get_object_or_404(
            LaborRole, pk=int(labor_id), plant=quote.plant, is_active=True
        )
    elif labor_id:
        labor = get_object_or_404(
            LaborRole, pk=int(labor_id), plant=quote.plant, is_active=True
        )

    return material, machine, labor


def _save_one_block(quote, post, prefix: str) -> QuoteProcess | None:
    """
    Save one process block. prefix e.g. 'block-0-'.
    Returns None if process_id empty (blank block skipped).
    """
    process_id = (post.get(f"{prefix}process_id") or "").strip()
    if not process_id:
        return None

    process = get_object_or_404(
        Process.objects.prefetch_related("fields", "subprocesses__fields"),
        pk=int(process_id),
        plant=quote.plant,
        is_active=True,
    )
    material, machine, labor = _resolve_optional_catalog(quote, process, post, prefix)

    qp_id = (post.get(f"{prefix}qp_id") or "").strip()
    if qp_id:
        qp = get_object_or_404(QuoteProcess, pk=int(qp_id), quote=quote)
        qp.process = process
        qp.material = material
        qp.machine = machine
        qp.labor_role = labor
        qp.save(update_fields=["process", "material", "machine", "labor_role"])
    else:
        qp = QuoteProcess.objects.create(
            quote=quote,
            process=process,
            material=material,
            machine=machine,
            labor_role=labor,
            sort_order=quote.quote_processes.count() * 10,
        )

    field_vals = _read_field_values(post, list(process.fields.all()), f"{prefix}fld_")
    QuoteProcessFieldValue.objects.filter(quote_process=qp).delete()
    for code, value in field_vals.items():
        QuoteProcessFieldValue.objects.create(
            quote_process=qp, field_code=code, value=value
        )

    sub_count = int(post.get(f"{prefix}sub_count") or 0)
    selected_ids: list[int] = []
    seen = set()
    for i in range(sub_count):
        raw = (post.get(f"{prefix}sub-{i}-id") or "").strip()
        if not raw:
            continue
        sp_id = int(raw)
        if sp_id in seen:
            continue
        seen.add(sp_id)
        selected_ids.append(sp_id)

    linked = {
        sp.pk: sp
        for sp in process.subprocesses.filter(is_active=True, pk__in=selected_ids)
    }
    qp.subprocesses.exclude(subprocess_id__in=linked.keys()).delete()

    for order, sp_id in enumerate(selected_ids):
        sp = linked.get(sp_id)
        if not sp:
            continue
        qs, _ = QuoteSubProcess.objects.get_or_create(
            quote_process=qp,
            subprocess=sp,
            defaults={"sort_order": order * 10},
        )
        qs.sort_order = order * 10
        qs.save(update_fields=["sort_order"])
        row_prefix = None
        for i in range(sub_count):
            if (post.get(f"{prefix}sub-{i}-id") or "").strip() == str(sp_id):
                row_prefix = f"{prefix}sub-{i}-fld_"
                break
        if row_prefix is None:
            continue
        sp_vals = _read_field_values(post, list(sp.fields.all()), row_prefix)
        QuoteSubProcessFieldValue.objects.filter(quote_subprocess=qs).delete()
        for code, value in sp_vals.items():
            QuoteSubProcessFieldValue.objects.create(
                quote_subprocess=qs, field_code=code, value=value
            )

    calculate_quote_process(qp)
    return qp


def save_wizard_process_blocks(quote, post) -> list[QuoteProcess]:
    """Save all process blocks from the multi-block wizard form."""
    total = int(post.get("block_count") or 0)
    saved = []
    kept_ids = set()
    for i in range(total):
        qp = _save_one_block(quote, post, f"block-{i}-")
        if qp is not None:
            saved.append(qp)
            kept_ids.add(qp.pk)

    initial_ids = {
        int(x) for x in post.getlist("initial_qp_ids") if str(x).isdigit()
    }
    stale = initial_ids - kept_ids
    if stale:
        quote.quote_processes.filter(pk__in=stale).delete()

    quote.status = quote.Status.DRAFT
    quote.save(update_fields=["status", "updated_at"])
    return saved


def available_processes(quote):
    return [
        {"id": p.pk, "label": f"{p.code} — {p.name}"}
        for p in Process.objects.filter(plant=quote.plant, is_active=True).order_by("code")
    ]
