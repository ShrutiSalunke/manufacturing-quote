"""
Metal weight calculator for the quote wizard.

Shapes use dimensions in the selected unit (converted to mm internally).
Density is g/cm³. Result weight is kg.
"""
from __future__ import annotations

import math
from typing import Any

# Default densities (g/cm³) when catalog material has no density
DEFAULT_METAL_DENSITIES = {
    "steel": 7.85,
    "mild steel": 7.85,
    "ms": 7.85,
    "stainless steel": 8.0,
    "ss": 8.0,
    "aluminium": 2.70,
    "aluminum": 2.70,
    "al": 2.70,
    "copper": 8.96,
    "brass": 8.50,
    "cast iron": 7.20,
}

UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}


SHAPES: list[dict[str, Any]] = [
    {
        "id": "round_bar",
        "label": "Round Bar",
        "diagram": "round_bar",
        "fields": [
            {"key": "diameter", "label": "Diameter (A)", "diagram_key": "A"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "pipe",
        "label": "Pipe",
        "diagram": "pipe",
        "fields": [
            {"key": "diameter", "label": "Diameter (A)", "diagram_key": "A"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "square_bar",
        "label": "Square Bar",
        "diagram": "square_bar",
        "fields": [
            {"key": "side", "label": "Side (A)", "diagram_key": "A"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "hex_bar",
        "label": "Hexagonal Bar",
        "diagram": "hex_bar",
        "fields": [
            {"key": "across_flats", "label": "Across flats (AF)", "diagram_key": "AF"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "square_tubing",
        "label": "Square Tubing",
        "diagram": "square_tubing",
        "fields": [
            {"key": "side", "label": "Outer side (A)", "diagram_key": "A"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "beam",
        "label": "Beam",
        "diagram": "beam",
        "fields": [
            {"key": "height", "label": "Height (H)", "diagram_key": "H"},
            {"key": "flange_width", "label": "Flange width (B)", "diagram_key": "B"},
            {"key": "web_thickness", "label": "Web thickness (Tw)", "diagram_key": "Tw"},
            {"key": "flange_thickness", "label": "Flange thickness (Tf)", "diagram_key": "Tf"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "t_bar",
        "label": "T-Bar",
        "diagram": "t_bar",
        "fields": [
            {"key": "flange_width", "label": "Flange width (B)", "diagram_key": "B"},
            {"key": "height", "label": "Height (H)", "diagram_key": "H"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "channel",
        "label": "Channel",
        "diagram": "channel",
        "fields": [
            {"key": "height", "label": "Height (H)", "diagram_key": "H"},
            {"key": "flange_width", "label": "Flange width (B)", "diagram_key": "B"},
            {"key": "web_thickness", "label": "Web thickness (Tw)", "diagram_key": "Tw"},
            {"key": "flange_thickness", "label": "Flange thickness (Tf)", "diagram_key": "Tf"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "angle",
        "label": "Angle",
        "diagram": "angle",
        "fields": [
            {"key": "leg_a", "label": "Leg A", "diagram_key": "A"},
            {"key": "leg_b", "label": "Leg B", "diagram_key": "B"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "flat_bar",
        "label": "Flat Bar",
        "diagram": "flat_bar",
        "fields": [
            {"key": "width", "label": "Width (W)", "diagram_key": "W"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
            {"key": "length", "label": "Length", "diagram_key": "L"},
        ],
    },
    {
        "id": "sheet",
        "label": "Sheet",
        "diagram": "sheet",
        "fields": [
            {"key": "length", "label": "Length (L)", "diagram_key": "L"},
            {"key": "width", "label": "Width (W)", "diagram_key": "W"},
            {"key": "thickness", "label": "Thickness (T)", "diagram_key": "T"},
        ],
    },
]

SHAPE_BY_ID = {s["id"]: s for s in SHAPES}


def _to_mm(value: float, unit: str) -> float:
    factor = UNIT_TO_MM.get((unit or "mm").lower(), 1.0)
    return float(value) * factor


def _mm3_to_kg(volume_mm3: float, density_g_cm3: float) -> float:
    # mass_g = (mm³ / 1000) * density; mass_kg = mass_g / 1000
    return (volume_mm3 * float(density_g_cm3)) / 1_000_000.0


def _volume_mm3(shape_id: str, dims_mm: dict[str, float]) -> float:
    if shape_id == "round_bar":
        d = dims_mm["diameter"]
        return math.pi * (d / 2.0) ** 2 * dims_mm["length"]

    if shape_id == "pipe":
        od = dims_mm["diameter"]
        t = dims_mm["thickness"]
        if t * 2 >= od:
            raise ValueError("Thickness too large for diameter.")
        id_ = od - 2 * t
        return math.pi * ((od / 2.0) ** 2 - (id_ / 2.0) ** 2) * dims_mm["length"]

    if shape_id == "square_bar":
        a = dims_mm["side"]
        return a * a * dims_mm["length"]

    if shape_id == "hex_bar":
        af = dims_mm["across_flats"]
        # Area across flats = (√3 / 2) * AF²
        return (math.sqrt(3) / 2.0) * af * af * dims_mm["length"]

    if shape_id == "square_tubing":
        a = dims_mm["side"]
        t = dims_mm["thickness"]
        if t * 2 >= a:
            raise ValueError("Thickness too large for side.")
        inner = a - 2 * t
        return (a * a - inner * inner) * dims_mm["length"]

    if shape_id == "beam":
        h = dims_mm["height"]
        b = dims_mm["flange_width"]
        tw = dims_mm["web_thickness"]
        tf = dims_mm["flange_thickness"]
        # Two flanges + web between flanges
        area = 2 * b * tf + (h - 2 * tf) * tw
        if area <= 0:
            raise ValueError("Invalid beam dimensions.")
        return area * dims_mm["length"]

    if shape_id == "t_bar":
        b = dims_mm["flange_width"]
        h = dims_mm["height"]
        t = dims_mm["thickness"]
        area = b * t + (h - t) * t
        return area * dims_mm["length"]

    if shape_id == "channel":
        h = dims_mm["height"]
        b = dims_mm["flange_width"]
        tw = dims_mm["web_thickness"]
        tf = dims_mm["flange_thickness"]
        area = h * tw + 2 * (b - tw) * tf
        if area <= 0:
            raise ValueError("Invalid channel dimensions.")
        return area * dims_mm["length"]

    if shape_id == "angle":
        a = dims_mm["leg_a"]
        b = dims_mm["leg_b"]
        t = dims_mm["thickness"]
        area = (a + b - t) * t
        return area * dims_mm["length"]

    if shape_id == "flat_bar":
        return dims_mm["width"] * dims_mm["thickness"] * dims_mm["length"]

    if shape_id == "sheet":
        return dims_mm["length"] * dims_mm["width"] * dims_mm["thickness"]

    raise ValueError(f"Unknown shape: {shape_id}")


def _length_key(shape_id: str) -> str:
    return "length"


def calculate(
    *,
    shape_id: str,
    density: float,
    mode: str = "by_length",
    pieces: float = 1,
    price_per_kg: float = 0,
    dimensions: dict[str, Any] | None = None,
    units: dict[str, str] | None = None,
    target_weight_kg: float | None = None,
) -> dict[str, Any]:
    """
    mode=by_length: compute weight from dimensions.
    mode=by_weight: invert for length given target_weight_kg (total for all pieces).
    """
    shape = SHAPE_BY_ID.get(shape_id)
    if not shape:
        raise ValueError("Select a raw material shape.")
    if density <= 0:
        raise ValueError("Density must be greater than zero.")
    pieces = max(float(pieces or 1), 0.0001)
    dimensions = dimensions or {}
    units = units or {}

    dims_mm: dict[str, float] = {}
    for f in shape["fields"]:
        key = f["key"]
        if mode == "by_weight" and key == _length_key(shape_id):
            continue
        raw = dimensions.get(key)
        if raw in (None, ""):
            raise ValueError(f"{f['label']} is required.")
        dims_mm[key] = _to_mm(float(raw), units.get(key, "mm"))

    length_key = _length_key(shape_id)

    if mode == "by_weight":
        if target_weight_kg is None or float(target_weight_kg) <= 0:
            raise ValueError("Enter a target weight (kg).")
        # volume per mm of length
        probe = dict(dims_mm)
        probe[length_key] = 1.0
        vol_per_mm = _volume_mm3(shape_id, probe)
        if vol_per_mm <= 0:
            raise ValueError("Invalid dimensions.")
        kg_per_mm_one = _mm3_to_kg(vol_per_mm, density)
        kg_per_mm_all = kg_per_mm_one * pieces
        length_mm = float(target_weight_kg) / kg_per_mm_all
        dims_mm[length_key] = length_mm
        weight_one = _mm3_to_kg(_volume_mm3(shape_id, dims_mm), density)
        total_weight = weight_one * pieces
        length_out_mm = length_mm
    else:
        vol = _volume_mm3(shape_id, dims_mm)
        weight_one = _mm3_to_kg(vol, density)
        total_weight = weight_one * pieces
        length_out_mm = dims_mm.get(length_key, 0)

    total_cost = total_weight * float(price_per_kg or 0)
    return {
        "shape_id": shape_id,
        "shape_label": shape["label"],
        "mode": mode,
        "density": density,
        "pieces": pieces,
        "price_per_kg": float(price_per_kg or 0),
        "weight_kg_one": round(weight_one, 6),
        "weight_kg_total": round(total_weight, 6),
        "length_mm": round(length_out_mm, 4),
        "total_cost": round(total_cost, 4),
        "dimensions_mm": {k: round(v, 4) for k, v in dims_mm.items()},
    }


def resolve_density(material_density, metal_label: str, override) -> float:
    if override not in (None, ""):
        return float(override)
    if material_density not in (None, ""):
        return float(material_density)
    key = (metal_label or "").strip().lower()
    if key in DEFAULT_METAL_DENSITIES:
        return DEFAULT_METAL_DENSITIES[key]
    for name, dens in DEFAULT_METAL_DENSITIES.items():
        if name in key:
            return dens
    return 7.85
