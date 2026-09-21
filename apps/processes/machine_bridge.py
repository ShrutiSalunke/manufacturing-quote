"""
Optional machine → process-field auto-fill bridge.

Mirrors material_bridge: formulas use field codes; machine values fill fields
via machine_property_key when use_machine_properties is on.
"""
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import CustomFieldDefinition, CustomFieldValue, Machine

MACHINE_BRIDGE_ENABLED = True

BUILTIN_MACHINE_KEYS = {
    "hourly_rate": "hourly_rate",
    "setup_rate": "setup_rate",
    "efficiency_percent": "efficiency_percent",
    "code": "code",
    "name": "name",
}

BUILTIN_MACHINE_LABELS = {
    "hourly_rate": "Hourly rate",
    "setup_rate": "Setup rate",
    "efficiency_percent": "Efficiency %",
    "code": "Machine code",
    "name": "Machine name",
}

_NUMERIC_KEYS = frozenset({"hourly_rate", "setup_rate", "efficiency_percent"})


def machine_property_choices():
    choices = [("", "- None -")]
    for key, label in BUILTIN_MACHINE_LABELS.items():
        choices.append((key, f"{label} ({key})"))
    custom = (
        CustomFieldDefinition.objects.filter(
            entity_type=CustomFieldDefinition.EntityType.MACHINE,
            is_active=True,
        )
        .order_by("sort_order", "key")
        .values_list("key", "label")
    )
    for key, label in custom:
        choices.append((key, f"{label} ({key}) - custom"))
    return choices


def resolve_machine_property(machine: Machine | None, property_key: str):
    if not MACHINE_BRIDGE_ENABLED or not machine or not property_key:
        return None
    key = property_key.strip().lower()
    if key in BUILTIN_MACHINE_KEYS:
        return getattr(machine, BUILTIN_MACHINE_KEYS[key], None)
    ct = ContentType.objects.get_for_model(Machine)
    cfv = (
        CustomFieldValue.objects.filter(
            content_type=ct,
            object_id=machine.pk,
            definition__key__iexact=key,
            definition__is_active=True,
        )
        .select_related("definition")
        .first()
    )
    return cfv.get_value() if cfv else None
