"""Tests for transform module."""

import pytest
from unittest.mock import MagicMock

from transform import transform_records, _normalize_confidence, _make_value_str
from models import ExtractedRecord, TransformedRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_material_normalizer():
    """Return a MaterialNormalizer stub that echoes the input."""
    norm = MagicMock()
    norm.normalize.side_effect = lambda x: x
    return norm


# ===========================================================================
# TestTransformRecords
# ===========================================================================


class TestTransformRecords:
    """Tests for transform_records()."""

    def test_scalar_record_transforms(self, sample_scalar_record):
        """Scalar ExtractedRecord → TransformedRecord with correct fields."""
        norm = _mock_material_normalizer()
        results = transform_records([sample_scalar_record], norm)

        assert len(results) == 1
        tr = results[0]
        assert isinstance(tr, TransformedRecord)
        assert tr.id == "test-scalar-001"
        assert tr.name == "density"
        assert tr.category == "physical_property"
        assert tr.value_type == "scalar"
        assert tr.value_scalar == 15.6
        assert tr.unit is not None  # normalize_unit may alter, but must exist
        assert tr.material_raw == "U-10Zr"
        assert tr.temperature_k == 293.0

    def test_expression_record_preserves_latex(self, sample_expression_record):
        """LaTeX expression is preserved in value_expr."""
        norm = _mock_material_normalizer()
        results = transform_records([sample_expression_record], norm)

        assert len(results) == 1
        tr = results[0]
        assert tr.value_type == "expression"
        # value_expr should contain the expression (from value_expr or equation)
        assert tr.value_expr is not None
        assert "\\alpha" in tr.value_expr or "1.2e-5" in tr.value_expr

    def test_empty_input_returns_empty(self):
        """Empty list → empty list."""
        norm = _mock_material_normalizer()
        assert transform_records([], norm) == []


# ===========================================================================
# TestNormalizeConfidence
# ===========================================================================


class TestNormalizeConfidence:
    """Tests for _normalize_confidence()."""

    def test_known_levels(self):
        assert _normalize_confidence("high") == "high"
        assert _normalize_confidence("medium") == "medium"
        assert _normalize_confidence("low") == "low"

    def test_none_returns_none(self):
        assert _normalize_confidence(None) is None

    def test_case_insensitive(self):
        """Uppercase and mixed case are normalized to lowercase."""
        assert _normalize_confidence("HIGH") == "high"
        assert _normalize_confidence("Medium") == "medium"
        assert _normalize_confidence("LOW") == "low"

    def test_abbreviations(self):
        """Short forms h/m/l are accepted."""
        assert _normalize_confidence("h") == "high"
        assert _normalize_confidence("med") == "medium"
        assert _normalize_confidence("l") == "low"

    def test_unknown_returns_none(self):
        assert _normalize_confidence("garbage") is None
        assert _normalize_confidence("None") is None
        assert _normalize_confidence("null") is None


# ===========================================================================
# TestMakeValueStr
# ===========================================================================


class TestMakeValueStr:
    """Tests for _make_value_str()."""

    def test_scalar_to_string(self):
        """A scalar record produces a string containing the value."""
        rec = ExtractedRecord(
            record_id="v1",
            source_file="test.json",
            raw_value="15.6",
            value_scalar=15.6,
        )
        result = _make_value_str(rec)
        assert result is not None
        assert "15.6" in result

    def test_range_to_string(self):
        """A range record produces a string with min and max."""
        rec = ExtractedRecord(
            record_id="v2",
            source_file="test.json",
            raw_value="10–25",
            value_min=10.0,
            value_max=25.0,
        )
        result = _make_value_str(rec)
        assert result is not None
        assert "10" in result
        assert "25" in result

    def test_expression_preserved(self):
        """An expression record returns the raw expression text."""
        expr = "\\alpha = 1.2e-5 + 5.3e-9 * T"
        rec = ExtractedRecord(
            record_id="v3",
            source_file="test.json",
            raw_value=expr,
            value_expr=expr,
        )
        result = _make_value_str(rec)
        # value_str is None so falls through to raw_value
        assert result is not None
        assert "1.2e-5" in result

    def test_value_str_takes_priority(self):
        """If value_str is already set, it is returned as-is."""
        rec = ExtractedRecord(
            record_id="v4",
            source_file="test.json",
            raw_value="42",
            value_str="custom value string",
        )
        assert _make_value_str(rec) == "custom value string"

    def test_none_raw_value_returns_none(self):
        """If raw_value is None and value_str unset, returns None."""
        rec = ExtractedRecord(
            record_id="v5",
            source_file="test.json",
            raw_value=None,
        )
        assert _make_value_str(rec) is None
