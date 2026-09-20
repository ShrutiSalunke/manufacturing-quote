"""
Helpers so CustomFieldDefinition rows become real columns on Materials / Machines / Labor.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import CustomFieldDefinition, CustomFieldValue


def active_definitions(entity_type: str, plant=None):
    """Active custom field definitions for an entity (optionally scoped to plant)."""
    qs = CustomFieldDefinition.objects.filter(
        entity_type=entity_type,
        is_active=True,
    ).order_by("sort_order", "key")
    if plant is not None:
        qs = qs.filter(Q(plant__isnull=True) | Q(plant=plant))
    return list(qs)


def _content_type_for(obj):
    return ContentType.objects.get_for_model(obj.__class__)


def values_by_key(obj) -> dict:
    """Return {definition.key: display/raw value} for an object."""
    if not obj or not getattr(obj, "pk", None):
        return {}
    ct = _content_type_for(obj)
    out = {}
    for cfv in CustomFieldValue.objects.filter(
        content_type=ct, object_id=obj.pk, definition__is_active=True
    ).select_related("definition"):
        out[cfv.definition.key] = cfv.get_value()
    return out


def display_value(raw, definition: CustomFieldDefinition) -> str:
    if raw is None or raw == "":
        return "—"
    if definition.data_type == CustomFieldDefinition.DataType.BOOL:
        return "Yes" if raw else "No"
    return str(raw)


def attach_custom_columns(objects, definitions):
    """
    Attach `.custom_display` dict {key: display_str} on each object for list tables.
    Bulk-loads values to avoid N+1.
    """
    objects = list(objects)
    if not objects or not definitions:
        for obj in objects:
            obj.custom_display = {}
            obj.custom_display_list = []
        return objects

    ct = ContentType.objects.get_for_model(objects[0].__class__)
    ids = [o.pk for o in objects]
    keys = {d.key for d in definitions}
    by_obj: dict[int, dict] = {pk: {} for pk in ids}
    for cfv in CustomFieldValue.objects.filter(
        content_type=ct,
        object_id__in=ids,
        definition__key__in=keys,
        definition__is_active=True,
    ).select_related("definition"):
        by_obj[cfv.object_id][cfv.definition.key] = display_value(
            cfv.get_value(), cfv.definition
        )

    for obj in objects:
        filled = by_obj.get(obj.pk, {})
        obj.custom_display = {
            d.key: filled.get(d.key, "—") for d in definitions
        }
        obj.custom_display_list = [obj.custom_display[d.key] for d in definitions]
    return objects


def detail_rows(obj, definitions):
    """List of {label, value} for detail pages."""
    vals = values_by_key(obj)
    return [
        {
            "key": d.key,
            "label": d.label,
            "value": display_value(vals.get(d.key), d),
        }
        for d in definitions
    ]


class CustomFieldValuesForm(forms.Form):
    """Dynamic form fields named cf_<key> for active custom definitions."""

    def __init__(self, *args, definitions=None, instance=None, **kwargs):
        self.definitions = list(definitions or [])
        super().__init__(*args, **kwargs)
        existing = values_by_key(instance) if instance is not None else {}

        for d in self.definitions:
            name = f"cf_{d.key}"
            initial = existing.get(d.key)
            required = bool(d.is_required)
            help_text = ""
            if d.data_type == CustomFieldDefinition.DataType.NUMBER:
                self.fields[name] = forms.DecimalField(
                    label=d.label,
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.NumberInput(attrs={"class": "form-control mq-input", "step": "any"}),
                )
            elif d.data_type == CustomFieldDefinition.DataType.DATE:
                if initial and hasattr(initial, "isoformat"):
                    initial = initial.isoformat()
                self.fields[name] = forms.DateField(
                    label=d.label,
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.DateInput(attrs={"class": "form-control mq-input", "type": "date"}),
                )
            elif d.data_type == CustomFieldDefinition.DataType.BOOL:
                self.fields[name] = forms.BooleanField(
                    label=d.label,
                    required=False,
                    initial=bool(initial) if initial is not None else False,
                    help_text=help_text,
                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                )
            elif d.data_type == CustomFieldDefinition.DataType.ENUM:
                choices = [("", "— Select —")] + [
                    (c, c) for c in (d.enum_choices or [])
                ]
                self.fields[name] = forms.ChoiceField(
                    label=d.label,
                    required=required,
                    choices=choices,
                    initial=initial or "",
                    help_text=help_text,
                    widget=forms.Select(attrs={"class": "form-select"}),
                )
            else:
                self.fields[name] = forms.CharField(
                    label=d.label,
                    required=required,
                    initial=initial if initial is not None else "",
                    help_text=help_text,
                    widget=forms.TextInput(attrs={"class": "form-control mq-input"}),
                )


def _coerce_value(definition: CustomFieldDefinition, raw):
    if raw is None or raw == "":
        return None
    dt = definition.data_type
    if dt == CustomFieldDefinition.DataType.NUMBER:
        if isinstance(raw, Decimal):
            return raw
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise forms.ValidationError(f"Invalid number for {definition.label}") from exc
    if dt == CustomFieldDefinition.DataType.DATE:
        if hasattr(raw, "year"):
            return raw
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    if dt == CustomFieldDefinition.DataType.BOOL:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")
    return str(raw)


def save_custom_field_values(obj, cleaned_data: dict, definitions) -> None:
    """Upsert CustomFieldValue rows from a CustomFieldValuesForm.cleaned_data."""
    ct = _content_type_for(obj)
    for d in definitions:
        name = f"cf_{d.key}"
        if name not in cleaned_data:
            continue
        raw = cleaned_data.get(name)
        # Unchecked bool → False
        if d.data_type == CustomFieldDefinition.DataType.BOOL:
            raw = bool(raw)
        value = _coerce_value(d, raw)
        cfv, _ = CustomFieldValue.objects.get_or_create(
            definition=d, content_type=ct, object_id=obj.pk
        )
        cfv.set_value(value)
        cfv.save()
