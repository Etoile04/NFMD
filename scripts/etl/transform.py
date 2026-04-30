"""Transform: Normalize records for database loading."""

import re
from typing import Optional

from models import ExtractedRecord, TransformedRecord
from normalize import MaterialNormalizer, normalize_unit, parse_temperature


def transform_records(
    records: list[ExtractedRecord],
    material_norm: MaterialNormalizer,
) -> list[TransformedRecord]:
    """Transform extracted records into database-ready format."""
    results = []
    for rec in records:
        transformed = _transform_one(rec, material_norm)
        if transformed:
            results.append(transformed)
    return results


def _transform_one(
    rec: ExtractedRecord, material_norm: MaterialNormalizer
) -> Optional[TransformedRecord]:
    """Transform a single record."""
    # Material normalization
    material_name = material_norm.normalize(rec.raw_material)

    # Temperature: use pre-extracted if available, otherwise parse
    temp_k = rec.temperature_K
    temp_str = rec.temperature_str
    if temp_k is None and rec.raw_temperature:
        parsed_k, parsed_str = parse_temperature(rec.raw_temperature)
        if parsed_k:
            temp_k = parsed_k
        if parsed_str:
            temp_str = parsed_str

    # Unit normalization
    unit = normalize_unit(rec.raw_unit)

    # Confidence normalization
    confidence = _normalize_confidence(rec.raw_confidence)

    # Value decomposition
    value_scalar = rec.value_scalar
    value_min = rec.value_min
    value_max = rec.value_max
    value_expr = rec.value_expr
    value_list = rec.value_list
    value_text = rec.value_text
    value_str = rec.value_str or _make_value_str(rec)

    # Handle expression type: value might be in equation or value_str
    if rec.value_type == "expression":
        if not value_expr:
            if rec.equation and rec.equation not in ("Eq. 1", "Eq. 2", "Eq. 3"):
                value_expr = rec.equation
            elif isinstance(rec.raw_value, str):
                value_expr = rec.raw_value

    # Combine notes from multiple sources
    notes_parts = []
    if rec.notes:
        notes_parts.append(rec.notes)
    if rec.description:
        notes_parts.append(rec.description)
    if rec.phase:
        notes_parts.append(f"Phase: {rec.phase}")
    if rec.conditions:
        notes_parts.append(f"Conditions: {rec.conditions}")
    combined_notes = "; ".join(notes_parts) if notes_parts else None

    # Generate literature ID from source_file
    literature_id = _slug_from_source(rec.source_file)

    return TransformedRecord(
        id=rec.record_id,
        name=rec.name_en or rec.name,
        name_en=rec.name_en,
        name_zh=rec.name_zh or (rec.name if rec.name_en and rec.name != rec.name_en else None),
        symbol=rec.symbol,
        category=rec.category,
        subcategory=rec.subcategory,
        value_type=rec.value_type,
        value_scalar=value_scalar,
        value_min=value_min,
        value_max=value_max,
        value_expr=value_expr,
        value_list=value_list,
        value_text=value_text,
        value_str=value_str,
        unit=unit,
        uncertainty=rec.uncertainty if rec.uncertainty and rec.uncertainty != "None" else None,
        material_name=material_name,
        material_raw=rec.raw_material,
        temperature_k=temp_k,
        temperature_str=temp_str,
        burnup_range=rec.raw_burnup,
        method=rec.raw_method,
        confidence=confidence,
        source_file=rec.source_file,
        equation=rec.equation,
        notes=combined_notes,
        literature_id=literature_id,
    )


def _normalize_confidence(raw: Optional[str]) -> Optional[str]:
    """Normalize confidence value."""
    if not raw or raw in ("None", "none", "null"):
        return None
    raw = raw.lower().strip()
    if raw in ("high", "h"):
        return "high"
    if raw in ("medium", "med", "m"):
        return "medium"
    if raw in ("low", "l"):
        return "low"
    return None


def _make_value_str(rec: ExtractedRecord) -> Optional[str]:
    """Generate value_str from available data."""
    if rec.value_str:
        return rec.value_str
    if rec.raw_value is not None:
        if isinstance(rec.raw_value, list):
            return ", ".join(str(v) for v in rec.raw_value)
        return str(rec.raw_value)
    return None


def _slug_from_source(source_file: str) -> str:
    """Generate a stable literature ID from source_file."""
    if not source_file:
        return "unknown"
    # Remove path and extension
    slug = source_file.replace("summaries/", "").replace("\\", "/").split("/")[-1]
    slug = slug.replace(".md", "").replace(".json", "").strip()
    # Truncate if too long
    if len(slug) > 120:
        slug = slug[:120]
    return slug
