"""Data models for ETL pipeline."""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class ExtractedRecord:
    """Intermediate record from extract stage — preserves raw facts."""
    record_id: str
    source_file: str
    source_paper: Optional[str] = None
    name: str = ""
    name_en: Optional[str] = None
    name_zh: Optional[str] = None
    symbol: Optional[str] = None
    category: str = ""
    subcategory: Optional[str] = None
    value_type: str = ""
    raw_value: Any = None
    raw_unit: Optional[str] = None
    raw_material: Optional[str] = None
    raw_temperature: Optional[Any] = None  # could be number or string
    raw_burnup: Optional[str] = None
    raw_method: Optional[str] = None
    raw_confidence: Optional[str] = None
    equation: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    phase: Optional[str] = None
    conditions: Optional[str] = None
    uncertainty: Optional[str] = None
    # Pre-extracted typed values (from source JSON)
    value_scalar: Optional[float] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_expr: Optional[str] = None
    value_list: Optional[list] = None
    value_text: Optional[str] = None
    value_str: Optional[str] = None
    temperature_K: Optional[float] = None
    temperature_str: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ValidationIssue:
    """A validation issue for a record."""
    run_id: str
    severity: str  # fatal, error, warn
    stage: str
    source_file: str
    record_id: str
    code: str
    message: str
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TransformedRecord:
    """Normalized record ready for database load."""
    id: str
    name: str
    name_en: Optional[str] = None
    name_zh: Optional[str] = None
    symbol: Optional[str] = None
    category: str = ""
    subcategory: Optional[str] = None
    value_type: str = ""
    value_scalar: Optional[float] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_expr: Optional[str] = None
    value_list: Optional[Any] = None  # JSON-serializable
    value_text: Optional[str] = None
    value_str: Optional[str] = None
    unit: Optional[str] = None
    uncertainty: Optional[str] = None
    material_name: Optional[str] = None  # canonical name from alias map
    material_raw: Optional[str] = None
    temperature_k: Optional[float] = None
    temperature_str: Optional[str] = None
    burnup_range: Optional[str] = None
    method: Optional[str] = None
    confidence: Optional[str] = None
    source_file: Optional[str] = None
    equation: Optional[str] = None
    notes: Optional[str] = None
    # Literature metadata
    literature_id: Optional[str] = None
    literature_title: Optional[str] = None
    literature_authors: Optional[str] = None
    literature_year: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
