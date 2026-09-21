"""Evaluate process / subprocess formulas and roll up quote totals."""
from decimal import Decimal

from apps.costing.engine import FormulaError, evaluate_expression, validate_formula_against_fields, validate_identifier

from . import labor_bridge, machine_bridge, material_bridge


def _num(value, default=0.0):
    if value is None or value == "":
        return float(default)
    return float(value)


def build_field_context(field_defs, value_map: dict) -> dict:
    """Build formula context from field definitions + entered values."""
    ctx = {}
    for f in field_defs:
        code = (f.code or "").upper()
        if not validate_identifier(code):
            raise FormulaError(f"Invalid field code: {code}")
        raw = value_map.get(f.code, value_map.get(code, f.default_value))
        if f.data_type == "number":
            if (raw is None or raw == "") and not f.is_required:
                ctx[code] = 0.0
            else:
                try:
                    ctx[code] = float(raw)
                except (TypeError, ValueError) as exc:
                    raise FormulaError(f"Field {code} must be a number") from exc
                if f.min_value is not None and ctx[code] < float(f.min_value):
                    raise FormulaError(f"Field {code} below minimum {f.min_value}")
                if f.max_value is not None and ctx[code] > float(f.max_value):
                    raise FormulaError(f"Field {code} above maximum {f.max_value}")
        elif f.data_type == "bool":
            if isinstance(raw, bool):
                ctx[code] = 1.0 if raw else 0.0
            else:
                ctx[code] = 1.0 if str(raw).strip().lower() in ("1", "true", "yes", "y") else 0.0
        else:
            ctx[code] = str(raw) if raw is not None else ""
            if f.is_required and ctx[code] == "":
                raise FormulaError(f"Field {code} is required")
    return ctx


def evaluate_entity_formula(entity, field_defs, value_map: dict, material=None) -> dict:
    """
    Evaluate result_formula for a Process or SubProcess.
    Formula may only use field codes (+ constants / safe math). Materials are applied
    earlier via auto-fill into field values — never as MAT_* names in the formula.
    Returns {value, unit, context, formula}.
    """
    ctx = build_field_context(field_defs, value_map)
    formula = (entity.result_formula or "0").strip() or "0"
    allowed = [(f.code or "").upper() for f in field_defs]
    validate_formula_against_fields(formula, allowed)
    value = _num(evaluate_expression(formula, ctx))
    return {
        "value": round(value, 6),
        "unit": entity.result_unit,
        "formula": formula,
        "context": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in ctx.items()},
    }


def calculate_quote_process(qp) -> dict:
    """Compute own + subprocess totals for one QuoteProcess; persist snapshots."""
    process = qp.process
    value_map = {fv.field_code: fv.value for fv in qp.field_values.all()}
    # Auto-fill from catalog property keys when empty
    if process.use_material_properties and qp.material_id:
        for f in process.fields.all():
            if f.material_property_key and not value_map.get(f.code):
                resolved = material_bridge.resolve_material_property(
                    qp.material, f.material_property_key
                )
                if resolved is not None and resolved != "":
                    value_map[f.code] = str(resolved)
    if process.use_machine_properties and qp.machine_id:
        for f in process.fields.all():
            if f.machine_property_key and not value_map.get(f.code):
                resolved = machine_bridge.resolve_machine_property(
                    qp.machine, f.machine_property_key
                )
                if resolved is not None and resolved != "":
                    value_map[f.code] = str(resolved)
    if process.use_labor_properties and qp.labor_role_id:
        for f in process.fields.all():
            if f.labor_property_key and not value_map.get(f.code):
                resolved = labor_bridge.resolve_labor_property(
                    qp.labor_role, f.labor_property_key
                )
                if resolved is not None and resolved != "":
                    value_map[f.code] = str(resolved)

    own = evaluate_entity_formula(
        process, list(process.fields.all()), value_map, material=qp.material
    )
    sub_results = []
    sub_sum = 0.0
    for qs in qp.subprocesses.select_related("subprocess").prefetch_related(
        "field_values", "subprocess__fields"
    ):
        sp = qs.subprocess
        sp_map = {fv.field_code: fv.value for fv in qs.field_values.all()}
        if sp.use_material_properties and qp.material_id:
            for f in sp.fields.all():
                if f.material_property_key and not sp_map.get(f.code):
                    resolved = material_bridge.resolve_material_property(
                        qp.material, f.material_property_key
                    )
                    if resolved is not None and resolved != "":
                        sp_map[f.code] = str(resolved)
        if sp.use_machine_properties and qp.machine_id:
            for f in sp.fields.all():
                if f.machine_property_key and not sp_map.get(f.code):
                    resolved = machine_bridge.resolve_machine_property(
                        qp.machine, f.machine_property_key
                    )
                    if resolved is not None and resolved != "":
                        sp_map[f.code] = str(resolved)
        if sp.use_labor_properties and qp.labor_role_id:
            for f in sp.fields.all():
                if f.labor_property_key and not sp_map.get(f.code):
                    resolved = labor_bridge.resolve_labor_property(
                        qp.labor_role, f.labor_property_key
                    )
                    if resolved is not None and resolved != "":
                        sp_map[f.code] = str(resolved)
        result = evaluate_entity_formula(
            sp, list(sp.fields.all()), sp_map, material=qp.material
        )
        qs.computed_value = Decimal(str(result["value"]))
        qs.snapshot = result
        qs.save(update_fields=["computed_value", "snapshot"])
        sub_sum += result["value"]
        sub_results.append(
            {
                "quote_subprocess_id": qs.pk,
                "code": sp.code,
                "name": sp.name,
                **result,
            }
        )

    total = own["value"] + sub_sum
    snap = {
        "own": own,
        "subprocesses": sub_results,
        "sub_sum": round(sub_sum, 6),
        "total": round(total, 6),
        "unit": process.result_unit,
    }
    qp.computed_own = Decimal(str(own["value"]))
    qp.computed_total = Decimal(str(total))
    qp.snapshot = snap
    qp.save(update_fields=["computed_own", "computed_total", "snapshot"])
    return snap


def calculate_quote_processes(quote) -> dict:
    """Calculate all quote processes; return rollup dict (does not touch template lines)."""
    processes_data = []
    money_total = 0.0
    time_total = 0.0
    for qp in quote.quote_processes.select_related(
        "process", "material", "machine", "labor_role"
    ).prefetch_related(
        "field_values",
        "process__fields",
        "subprocesses__field_values",
        "subprocesses__subprocess__fields",
    ):
        snap = calculate_quote_process(qp)
        processes_data.append(
            {
                "quote_process_id": qp.pk,
                "code": qp.process.code,
                "name": qp.process.name,
                "material_code": qp.material.code if qp.material_id else None,
                **snap,
            }
        )
        if qp.process.result_unit == "TIME":
            time_total += snap["total"]
        else:
            money_total += snap["total"]

    return {
        "processes": processes_data,
        "totals": {
            "process_money": round(money_total, 4),
            "process_time": round(time_total, 4),
        },
    }
