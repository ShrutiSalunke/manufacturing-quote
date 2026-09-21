"""
Optional labor role → process-field auto-fill bridge.

Mirrors material_bridge: formulas use field codes; labor values fill fields
via labor_property_key when use_labor_properties is on.
"""
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import CustomFieldDefinition, CustomFieldValue, LaborRole

LABOR_BRIDGE_ENABLED = True

BUILTIN_LABOR_KEYS = {
    "hourly_rate": "hourly_rate",
    "code": "code",
    "name": "name",
}

BUILTIN_LABOR_LABELS = {
    "hourly_rate": "Hourly rate",
    "code": "Labor code",
    "name": "Labor role name",
}


def labor_property_choices():
    choices = [("", "- None -")]
    for key, label in BUILTIN_LABOR_LABELS.items():
        choices.append((key, f"{label} ({key})"))
    custom = (
        CustomFieldDefinition.objects.filter(
            entity_type=CustomFieldDefinition.EntityType.LABOR,
            is_active=True,
        )
        .order_by("sort_order", "key")
        .values_list("key", "label")
    )
    for key, label in custom:
        choices.append((key, f"{label} ({key}) - custom"))
    return choices


def resolve_labor_property(role: LaborRole | None, property_key: str):
    if not LABOR_BRIDGE_ENABLED or not role or not property_key:
        return None
    key = property_key.strip().lower()
    if key in BUILTIN_LABOR_KEYS:
        return getattr(role, BUILTIN_LABOR_KEYS[key], None)
    ct = ContentType.objects.get_for_model(LaborRole)
    cfv = (
        CustomFieldValue.objects.filter(
            content_type=ct,
            object_id=role.pk,
            definition__key__iexact=key,
            definition__is_active=True,
        )
        .select_related("definition")
        .first()
    )
    return cfv.get_value() if cfv else None
