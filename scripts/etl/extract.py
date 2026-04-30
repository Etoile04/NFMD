"""Extract: Read source JSON files and generate unified intermediate records."""

import glob
import json
import os
from typing import Generator

from models import ExtractedRecord


def extract_records(source_dir: str) -> Generator[ExtractedRecord, None, None]:
    """Scan parameter JSON files and yield extracted records."""
    pattern = os.path.join(source_dir, "*.json")
    files = sorted(glob.glob(pattern))

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  [FATAL] Cannot parse {filename}: {e}")
            continue

        # Handle wrapper format
        if isinstance(data, dict):
            if "parameters" in data:
                records = data["parameters"]
            else:
                records = [data]  # single record as dict
        elif isinstance(data, list):
            records = data
        else:
            print(f"  [WARN] Unexpected format in {filename}: {type(data)}")
            continue

        for rec in records:
            if not isinstance(rec, dict):
                continue
            yield _to_extracted_record(rec, filename)


def _to_extracted_record(rec: dict, filename: str) -> ExtractedRecord:
    """Convert a raw JSON record to ExtractedRecord."""
    # Extract value based on value_type hints
    value_type = rec.get("value_type", "")
    raw_value = rec.get("value")

    # Pre-resolve typed values from source
    value_scalar = None
    value_min = rec.get("value_min")
    value_max = rec.get("value_max")
    value_expr = rec.get("value_expr")
    value_list = rec.get("value_list")
    value_text = rec.get("value_text")

    # For scalar, try to parse raw_value
    if value_type == "scalar" and raw_value is not None:
        try:
            value_scalar = float(raw_value)
        except (ValueError, TypeError):
            value_scalar = None

    # For range with raw_value as list
    if value_type == "range" and isinstance(raw_value, list) and len(raw_value) == 2:
        if value_min is None:
            try:
                value_min = float(raw_value[0])
            except (ValueError, TypeError):
                pass
        if value_max is None:
            try:
                value_max = float(raw_value[1])
            except (ValueError, TypeError):
                pass

    # For list type, raw_value might be the list
    if value_type == "list" and isinstance(raw_value, list) and value_list is None:
        value_list = raw_value

    # Temperature handling — multiple possible field names
    temp_raw = rec.get("temperature") or rec.get("temperature_K") or rec.get("temperature_range")
    temp_k = None
    temp_str = None
    if isinstance(temp_raw, (int, float)):
        temp_k = float(temp_raw)
        temp_str = str(temp_raw)
    elif isinstance(temp_raw, str):
        temp_str = temp_raw
    # Also check temperature_K explicitly
    if temp_k is None and rec.get("temperature_K"):
        try:
            temp_k = float(rec["temperature_K"])
        except (ValueError, TypeError):
            pass

    return ExtractedRecord(
        record_id=rec.get("id", ""),
        source_file=_clean_source_file(rec.get("source_file", filename)),
        source_paper=rec.get("source_paper"),
        name=rec.get("name", ""),
        name_en=rec.get("name_en"),
        name_zh=rec.get("name_zh"),
        symbol=rec.get("symbol"),
        category=rec.get("category", ""),
        subcategory=rec.get("subcategory"),
        value_type=value_type,
        raw_value=raw_value,
        raw_unit=rec.get("unit"),
        raw_material=rec.get("material"),
        raw_temperature=temp_raw,
        raw_burnup=rec.get("burnup_range"),
        raw_method=rec.get("method"),
        raw_confidence=rec.get("confidence"),
        equation=rec.get("equation"),
        notes=rec.get("notes") or rec.get("note"),
        description=rec.get("description"),
        phase=rec.get("phase"),
        conditions=rec.get("conditions"),
        uncertainty=rec.get("uncertainty"),
        value_scalar=value_scalar,
        value_min=value_min,
        value_max=value_max,
        value_expr=value_expr,
        value_list=value_list,
        value_text=value_text,
        value_str=rec.get("value_str") or (str(raw_value) if raw_value is not None else None),
        temperature_K=temp_k,
        temperature_str=temp_str,
    )


def _clean_source_file(source: str) -> str:
    """Clean source_file to just the filename stem."""
    if not source:
        return ""
    # Remove path prefix if any
    source = source.replace("summaries/", "").replace("summaries\\", "")
    # Remove .md extension if present (keep base name)
    if source.endswith(".md"):
        source = source[:-3]
    return source
