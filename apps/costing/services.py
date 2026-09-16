"""Cost rollup service for product templates and quote lines."""
from decimal import Decimal

from apps.core.logging_utils import log_event
from apps.costing.engine import FormulaError, evaluate_expression, topological_formula_order, validate_identifier
from apps.templates_engine.models import TemplateMarginRule


def _num(value, default=0.0):
    if value is None or value == "":
        return float(default)
    return float(value)


def build_context(parameter_values: dict, line_qty: float) -> dict:
    ctx = {"LINE_QTY": float(line_qty)}
    for code, val in parameter_values.items():
        if not validate_identifier(code):
            raise FormulaError(f"Invalid parameter code: {code}")
        try:
            ctx[code] = float(val)
        except (TypeError, ValueError):
            ctx[code] = val
    return ctx


def evaluate_named_formulas(template, ctx: dict, trace: list) -> dict:
    formulas = list(template.formulas.all())
    pairs = [(f.code, f.expression) for f in formulas]
    for code, _ in pairs:
        if not validate_identifier(code):
            raise FormulaError(f"Invalid formula code: {code}")
    order = topological_formula_order(pairs)
    by_code = {f.code: f for f in formulas}
    results = {}
    for code in order:
        f = by_code[code]
        local = {**ctx, **results}
        value = evaluate_expression(f.expression, local)
        results[code] = float(value)
        trace.append({"type": "formula", "code": code, "expression": f.expression, "value": results[code]})
    return results


def cost_template(template, parameter_values: dict, line_qty: float = 1.0) -> dict:
    """
    Run full cost rollup for a template with given parameters.
    Returns snapshot dict with materials, operations, cost_elements, totals, formula_trace.
    """
    trace = []
    ctx = build_context(parameter_values, line_qty)
    named = evaluate_named_formulas(template, ctx, trace)
    eval_ctx = {**ctx, **named}

    materials = []
    material_cost = 0.0
    for item in template.bom_items.select_related("material").all():
        local = dict(eval_ctx)
        mat = item.material
        if mat:
            local["UNIT_PRICE"] = _num(mat.unit_price)
            local["DENSITY"] = _num(mat.density, 0)
        qty_net = _num(evaluate_expression(item.qty_formula, local))
        scrap = _num(evaluate_expression(item.scrap_formula or "0", local))
        qty_buy = qty_net * (1 + scrap) * _num(line_qty)
        unit_price = _num(mat.unit_price) if mat else 0.0
        line_cost = qty_buy * unit_price
        material_cost += line_cost
        materials.append(
            {
                "name": item.name,
                "material_code": mat.code if mat else None,
                "qty_net": qty_net,
                "scrap": scrap,
                "qty_buy": qty_buy,
                "unit_price": unit_price,
                "cost": line_cost,
                "cost_group": item.cost_group,
            }
        )
        trace.append(
            {
                "type": "bom",
                "name": item.name,
                "qty_formula": item.qty_formula,
                "scrap_formula": item.scrap_formula,
                "qty_buy": qty_buy,
                "cost": line_cost,
            }
        )

    operations = []
    machine_cost = 0.0
    labor_cost = 0.0
    for op in template.operations.select_related("machine", "labor_role").all():
        local = dict(eval_ctx)
        efficiency = 1.0
        machine_hourly = 0.0
        setup_rate = 0.0
        if op.machine:
            machine_hourly = _num(op.machine.hourly_rate)
            setup_rate = _num(op.machine.setup_rate)
            efficiency = max(_num(op.machine.efficiency_percent, 100) / 100.0, 0.01)
            local["MACHINE_HOURLY_RATE"] = machine_hourly
            local["SETUP_RATE"] = setup_rate
            local["EFFICIENCY"] = efficiency
        labor_hourly = 0.0
        if op.labor_role:
            labor_hourly = _num(op.labor_role.hourly_rate)
            local["LABOR_HOURLY_RATE"] = labor_hourly

        setup_min = _num(evaluate_expression(op.setup_time_formula_min or "0", local))
        cycle_min = _num(evaluate_expression(op.cycle_time_formula_min or "0", local))
        labor_min = _num(evaluate_expression(op.labor_time_formula_min or "0", local))

        machine_hours = (setup_min + cycle_min * _num(line_qty)) / 60.0 / efficiency
        op_machine_cost = machine_hours * machine_hourly + (setup_min / 60.0) * setup_rate
        machine_cost += op_machine_cost

        labor_hours = (labor_min * _num(line_qty)) / 60.0
        op_labor_cost = labor_hours * labor_hourly
        labor_cost += op_labor_cost

        operations.append(
            {
                "sequence": op.sequence,
                "name": op.name,
                "machine_code": op.machine.code if op.machine else None,
                "labor_code": op.labor_role.code if op.labor_role else None,
                "setup_min": setup_min,
                "cycle_min": cycle_min,
                "labor_min": labor_min,
                "machine_hours": machine_hours,
                "labor_hours": labor_hours,
                "machine_cost": op_machine_cost,
                "labor_cost": op_labor_cost,
            }
        )
        trace.append(
            {
                "type": "operation",
                "name": op.name,
                "machine_cost": op_machine_cost,
                "labor_cost": op_labor_cost,
            }
        )

    eval_ctx["TOTAL_MATERIAL"] = material_cost
    eval_ctx["TOTAL_MACHINE"] = machine_cost
    eval_ctx["TOTAL_LABOR"] = labor_cost

    cost_elements = []
    other_cost = 0.0
    for ce in template.cost_elements.all():
        amount = _num(evaluate_expression(ce.amount_formula, eval_ctx))
        other_cost += amount
        cost_elements.append(
            {
                "code": ce.code,
                "name": ce.name,
                "category": ce.category,
                "amount": amount,
            }
        )
        trace.append({"type": "cost_element", "code": ce.code, "amount": amount})

    total_cost = material_cost + machine_cost + labor_cost + other_cost
    eval_ctx["TOTAL_COST"] = total_cost

    selling = total_cost
    margin_percent = 0.0
    margin_method = "MARGIN_PERCENT"
    margin_value = "0"
    try:
        rule = template.margin_rule
        margin_method = rule.method
        margin_value = rule.value_or_formula
        if rule.method == TemplateMarginRule.Method.MARGIN_PERCENT:
            margin = _num(evaluate_expression(str(rule.value_or_formula), eval_ctx))
            if margin >= 100:
                raise FormulaError("Margin percent must be < 100")
            selling = total_cost / (1 - margin / 100.0) if (1 - margin / 100.0) else 0
        elif rule.method == TemplateMarginRule.Method.MARKUP_PERCENT:
            markup = _num(evaluate_expression(str(rule.value_or_formula), eval_ctx))
            selling = total_cost * (1 + markup / 100.0)
        elif rule.method == TemplateMarginRule.Method.FIXED_PRICE:
            selling = _num(evaluate_expression(str(rule.value_or_formula), eval_ctx))
    except TemplateMarginRule.DoesNotExist:
        pass

    if selling:
        margin_percent = (selling - total_cost) / selling * 100.0

    unit_selling = selling / _num(line_qty) if _num(line_qty) else selling

    return {
        "materials": materials,
        "operations": operations,
        "cost_elements": cost_elements,
        "totals": {
            "material": round(material_cost, 4),
            "machine": round(machine_cost, 4),
            "labor": round(labor_cost, 4),
            "overhead": round(other_cost, 4),
            "other": round(other_cost, 4),
            "total_cost": round(total_cost, 4),
            "selling_price": round(selling, 4),
            "unit_selling_price": round(unit_selling, 4),
            "margin_percent": round(margin_percent, 4),
            "margin_method": margin_method,
            "margin_value": margin_value,
            "line_qty": _num(line_qty),
        },
        "formula_trace": trace,
        "named_formulas": named,
        "parameters": parameter_values,
    }


def calculate_quote(quote, *, request=None, user=None):
    """Calculate all lines, persist snapshot, set status CALCULATED. Raises FormulaError."""
    from django.db import transaction

    from apps.quotes.models import Quote, QuoteCalculationSnapshot

    lines_data = []
    quote_totals = {
        "material": 0.0,
        "machine": 0.0,
        "labor": 0.0,
        "other": 0.0,
        "total_cost": 0.0,
        "selling_price": 0.0,
    }

    try:
        with transaction.atomic():
            for line in quote.lines.select_related("template").prefetch_related(
                "parameter_values",
                "template__formulas",
                "template__bom_items__material",
                "template__operations__machine",
                "template__operations__labor_role",
                "template__cost_elements",
            ):
                params = {pv.parameter_code: pv.value for pv in line.parameter_values.all()}
                # fill defaults
                for p in line.template.parameters.all():
                    if p.code not in params and p.default_value != "":
                        params[p.code] = p.default_value
                snap = cost_template(line.template, params, float(line.quantity))
                line.snapshot = snap
                line.save(update_fields=["snapshot"])
                lines_data.append(
                    {
                        "line_id": line.pk,
                        "description": line.description,
                        "quantity": float(line.quantity),
                        "template_code": line.template.code,
                        "template_version": line.template.version,
                        **snap,
                    }
                )
                t = snap["totals"]
                for k in ("material", "machine", "labor", "other", "total_cost", "selling_price"):
                    quote_totals[k] += t.get(k, 0)

            data = {"lines": lines_data, "totals": {k: round(v, 4) for k, v in quote_totals.items()}}
            QuoteCalculationSnapshot.objects.update_or_create(quote=quote, defaults={"data": data})
            quote.status = Quote.Status.CALCULATED
            quote.save(update_fields=["status", "updated_at"])
            return data
    except Exception as exc:
        entry = log_event(
            "ERROR",
            "costing",
            "COSTING",
            f"Costing failed for quote {quote.number}: {exc}",
            user=user,
            request=request,
            exc=exc,
            context={"quote_id": quote.pk, "quote_number": quote.number},
        )
        cid = entry.correlation_id if entry else None
        if isinstance(exc, FormulaError):
            exc.correlation_id = cid
            raise
        err = FormulaError(str(exc))
        err.correlation_id = cid
        raise err from exc
