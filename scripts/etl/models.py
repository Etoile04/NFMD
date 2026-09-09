"""Data models for ETL pipeline."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExtractedRecord:
    """Intermediate record from extract stage — preserves raw facts."""
    record_id: str
    source_file: str
    source_paper: str | None = None
    name: str = ""
    name_en: str | None = None
    name_zh: str | None = None
    symbol: str | None = None
    category: str = ""
    subcategory: str | None = None
    value_type: str = ""
    raw_value: Any = None
    raw_unit: str | None = None
    raw_material: str | None = None
    raw_temperature: Any | None = None  # could be number or string
    raw_burnup: str | None = None
    raw_method: str | None = None
    raw_confidence: str | None = None
    equation: str | None = None
    notes: str | None = None
    description: str | None = None
    phase: str | None = None
    conditions: str | None = None
    uncertainty: str | None = None
    # Pre-extracted typed values (from source JSON)
    value_scalar: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_expr: str | None = None
    value_list: list | None = None
    value_text: str | None = None
    value_str: str | None = None
    temperature_K: float | None = None
    temperature_str: str | None = None

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
    name_en: str | None = None
    name_zh: str | None = None
    symbol: str | None = None
    category: str = ""
    subcategory: str | None = None
    value_type: str = ""
    value_scalar: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_expr: str | None = None
    value_list: Any | None = None  # JSON-serializable
    value_text: str | None = None
    value_str: str | None = None
    unit: str | None = None
    uncertainty: str | None = None
    material_name: str | None = None  # canonical name from alias map
    material_raw: str | None = None
    temperature_k: float | None = None
    temperature_str: str | None = None
    burnup_range: str | None = None
    method: str | None = None
    confidence: str | None = None
    source_file: str | None = None
    equation: str | None = None
    notes: str | None = None
    # Literature metadata
    literature_id: str | None = None
    literature_title: str | None = None
    literature_authors: str | None = None
    literature_year: int | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LoadStats:
    """load 阶段的结果语义（ADR-0002）。

    计数与错误清单进 interface；致命失败不是一种 stats 取值，
    由 load.LoadFatalError 表达。
    """

    parameters_inserted: int = 0
    parameters_updated: int = 0
    parameters_skipped: int = 0
    parameters_errored: int = 0
    literature_upserted: int = 0
    literature_errors: int = 0
    material_resolved: int = 0
    material_unresolved: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
