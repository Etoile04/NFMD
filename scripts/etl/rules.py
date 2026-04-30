"""Validation rule definitions."""

from typing import Callable
from models import ExtractedRecord, ValidationIssue


# Allowed value types
VALID_VALUE_TYPES = {"scalar", "range", "expression", "list", "text"}

# Allowed confidence values
VALID_CONFIDENCE = {"high", "medium", "low"}

# Allowed categories (from knowledge base validate output + schema)
VALID_CATEGORIES = {
    "activation_energy", "bubble", "bubble_characteristics", "bubble_nucleation",
    "bubble_property", "corrosion", "creep", "crystal_structure",
    "defect_energetics", "diffusion", "diffusion_parameter", "elastic",
    "experiment", "fabrication", "fcci", "fission_product",
    "fuel_design", "fuel_performance", "irradiation", "irradiation_condition",
    "irradiation_creep", "irradiation_damage", "irradiation_parameter",
    "material_composition", "material_processing", "material_property",
    "measurement", "mechanical", "microstructure", "model_parameter",
    "nucleation", "other", "phase_field", "phase_field_parameter",
    "phase_transformation", "physical", "rate_theory", "recrystallization",
    "redistribution", "simulation", "simulation_parameter", "surface_energy",
    "swelling", "swelling_model", "swelling_rate", "swelling_result",
    "thermal", "thermodynamic", "unknown",
}


class Rule:
    """A validation rule that checks a record and returns issues."""

    def __init__(self, code: str, severity: str, check: Callable):
        self.code = code
        self.severity = severity  # fatal, error, warn
        self.check = check

    def apply(self, record: ExtractedRecord, run_id: str) -> list[ValidationIssue]:
        results = self.check(record)
        return [
            ValidationIssue(
                run_id=run_id,
                severity=self.severity,
                stage="validate",
                source_file=record.source_file,
                record_id=record.record_id,
                code=self.code,
                message=msg,
                context={"value_type": record.value_type, "category": record.category, "material": record.raw_material},
            )
            for msg in results
        ]


def _check_missing_id(rec: ExtractedRecord) -> list[str]:
    if not rec.record_id:
        return ["Missing record id"]
    return []


def _check_missing_name(rec: ExtractedRecord) -> list[str]:
    if not rec.name and not rec.name_en:
        return ["Missing both name and name_en"]
    return []


def _check_missing_category(rec: ExtractedRecord) -> list[str]:
    if not rec.category:
        return ["Missing category"]
    return []


def _check_invalid_category(rec: ExtractedRecord) -> list[str]:
    if rec.category and rec.category not in VALID_CATEGORIES:
        return [f"Unknown category '{rec.category}'"]
    return []


def _check_missing_value_type(rec: ExtractedRecord) -> list[str]:
    if not rec.value_type:
        return ["Missing value_type"]
    return []


def _check_invalid_value_type(rec: ExtractedRecord) -> list[str]:
    if rec.value_type and rec.value_type not in VALID_VALUE_TYPES:
        return [f"Invalid value_type '{rec.value_type}'"]
    return []


def _check_scalar_value(rec: ExtractedRecord) -> list[str]:
    if rec.value_type == "scalar":
        if rec.value_scalar is None and rec.raw_value is None:
            return ["scalar type but no value_scalar or raw_value"]
    return []


def _check_range_value(rec: ExtractedRecord) -> list[str]:
    if rec.value_type == "range":
        if rec.value_min is None and rec.value_max is None:
            # Check if raw_value is a list of 2 elements
            if isinstance(rec.raw_value, list) and len(rec.raw_value) == 2:
                return []  # Will be resolved in transform
            if rec.raw_value is not None:
                return []  # raw_value exists, transform will try to parse
            return ["range type but no value_min/value_max"]
    return []


def _check_expression_value(rec: ExtractedRecord) -> list[str]:
    if rec.value_type == "expression":
        if not rec.value_expr and not rec.equation and rec.raw_value is None:
            if not rec.value_str:  # value_str might contain the expression
                return ["expression type but no value_expr/equation/raw_value/value_str"]
    return []


def _check_list_value(rec: ExtractedRecord) -> list[str]:
    if rec.value_type == "list":
        if rec.value_list is None and not isinstance(rec.raw_value, list):
            return ["list type but no value_list and raw_value is not a list"]
    return []


def _check_missing_material(rec: ExtractedRecord) -> list[str]:
    if not rec.raw_material:
        return ["Missing material field"]
    return []


def _check_missing_source_file(rec: ExtractedRecord) -> list[str]:
    if not rec.source_file:
        return ["Missing source_file"]
    return []


def _check_confidence(rec: ExtractedRecord) -> list[str]:
    if rec.raw_confidence and rec.raw_confidence not in VALID_CONFIDENCE:
        return [f"Invalid confidence '{rec.raw_confidence}'"]
    return []


# All rules, ordered by severity
ALL_RULES: list[Rule] = [
    # Fatal (blocks entire run)
    # (none at record level — fatal is for systemic issues handled in extract)

    # Error (blocks this record)
    Rule("MISSING_ID", "error", _check_missing_id),
    Rule("MISSING_NAME", "error", _check_missing_name),
    Rule("MISSING_CATEGORY", "error", _check_missing_category),
    Rule("INVALID_CATEGORY", "warn", _check_invalid_category),
    Rule("MISSING_VALUE_TYPE", "error", _check_missing_value_type),
    Rule("INVALID_VALUE_TYPE", "error", _check_invalid_value_type),
    Rule("SCALAR_NO_VALUE", "error", _check_scalar_value),
    Rule("RANGE_NO_BOUNDS", "error", _check_range_value),
    Rule("EXPR_NO_FORMULA", "warn", _check_expression_value),
    Rule("LIST_NO_VALUES", "error", _check_list_value),

    # Warn (proceeds but logged)
    Rule("MISSING_MATERIAL", "warn", _check_missing_material),
    Rule("MISSING_SOURCE", "warn", _check_missing_source_file),
    Rule("INVALID_CONFIDENCE", "warn", _check_confidence),
]
