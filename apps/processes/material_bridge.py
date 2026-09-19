"""
Optional material → formula context bridge.

Disable globally by setting MATERIAL_BRIDGE_ENABLED = False.
Per-process/subprocess also has use_material_properties.

Materials are applied ONLY by auto-filling process/subprocess field values
(via material_property_key). Formulas must reference those field codes — never MAT_* names.
"""
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import CustomFieldDefinition, CustomFieldValue, Material

# Flip to False to disable material property injection app-wide (no other code changes needed).
MATERIAL_BRIDGE_ENABLED = True

# Built-in Material columns exposed as MAT_<NAME>
BUILTIN_MATERIAL_KEYS = {
    "unit_price": "unit_price",
    "density": "density",
    "uom": "uom",
    "code": "code",
    "name": "name",
    "category": "category",
    "currency": "currency",
}

# Human labels for the auto-fill dropdown
BUILTIN_MATERIAL_LABELS = {
    "unit_price": "Unit price",
    "density": "Density",
    "uom": "Unit of measure (UOM)",
    "code": "Material code",
    "name": "Material name",
    "category": "Category",
    "currency": "Currency",
}


def material_property_choices():
    """
    Choices for the Auto-fill from material dropdown.
    Built-in Material columns + active MATERIAL custom fields.
    """
    choices = [("", "- None -")]
    for key, label in BUILTIN_MATERIAL_LABELS.items():
        choices.append((key, f"{label} ({key})"))
    custom = (
        CustomFieldDefinition.objects.filter(
            entity_type=CustomFieldDefinition.EntityType.MATERIAL,
            is_active=True,
        )
        .order_by("sort_order", "key")
        .values_list("key", "label")
    )
    for key, label in custom:
        choices.append((key, f"{label} ({key}) - custom"))
    return choices


def material_context(material: Material | None) -> dict:
    """
    Return formula namespaced vars for a material.
    Keys: MAT_UNIT_PRICE, MAT_DENSITY, MAT_<CUSTOM_KEY>, etc.
    """
    if not MATERIAL_BRIDGE_ENABLED or material is None:
        return {}

    ctx: dict = {}
    for key, attr in BUILTIN_MATERIAL_KEYS.items():
        raw = getattr(material, attr, None)
        name = f"MAT_{key.upper()}"
        try:
            ctx[name] = float(raw) if raw is not None and raw != "" and key in (
                "unit_price",
                "density",
            ) else (raw if raw is not None else "")
        except (TypeError, ValueError):
            ctx[name] = raw

    ct = ContentType.objects.get_for_model(Material)
    for cfv in CustomFieldValue.objects.filter(
        content_type=ct, object_id=material.pk, definition__is_active=True
    ).select_related("definition"):
        key = (cfv.definition.key or "").upper()
        if not key:
            continue
        val = cfv.get_value()
        name = f"MAT_{key}"
        if cfv.definition.data_type == CustomFieldDefinition.DataType.NUMBER:
            try:
                ctx[name] = float(val) if val is not None else 0.0
            except (TypeError, ValueError):
                ctx[name] = 0.0
        else:
            ctx[name] = val if val is not None else ""
    return ctx


def resolve_material_property(material: Material | None, property_key: str):
    """Resolve a single property key for auto-fill into a process field."""
    if not MATERIAL_BRIDGE_ENABLED or not material or not property_key:
        return None
    key = property_key.strip().lower()
    if key in BUILTIN_MATERIAL_KEYS:
        return getattr(material, BUILTIN_MATERIAL_KEYS[key], None)
    ct = ContentType.objects.get_for_model(Material)
    cfv = (
        CustomFieldValue.objects.filter(
            content_type=ct,
            object_id=material.pk,
            definition__key__iexact=key,
            definition__is_active=True,
        )
        .select_related("definition")
        .first()
    )
    return cfv.get_value() if cfv else None
