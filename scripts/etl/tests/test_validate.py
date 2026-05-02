"""Tests for validate.py and rules.py."""

import pytest

from validate import validate_records
from rules import ALL_RULES


# ---------------------------------------------------------------------------
# TestValidateRecords — integration tests for validate_records()
# ---------------------------------------------------------------------------


class TestValidateRecords:
    """Tests for validate_records() return-value semantics."""

    def test_valid_scalar_record_no_fatal(
        self, sample_scalar_record
    ):
        valid, errored, issues = validate_records(
            [sample_scalar_record], "run-001"
        )
        assert len(valid) == 1
        assert len(errored) == 0
        # Scalar record may produce warnings (e.g. MISSING_SOURCE) but no errors
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_valid_range_record_no_fatal(
        self, sample_range_record
    ):
        valid, errored, issues = validate_records(
            [sample_range_record], "run-002"
        )
        assert len(valid) == 1
        assert len(errored) == 0
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_malformed_record_errored(
        self, malformed_record
    ):
        valid, errored, issues = validate_records(
            [malformed_record], "run-003"
        )
        # malformed has empty id, None name, empty category → errors
        assert len(valid) == 0
        assert len(errored) == 1
        assert errored[0] is malformed_record
        # Must have at least one error-level issue
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) >= 1

    def test_mixed_valid_and_invalid(
        self, sample_scalar_record, malformed_record
    ):
        valid, errored, issues = validate_records(
            [sample_scalar_record, malformed_record], "run-004"
        )
        assert len(valid) == 1
        assert len(errored) == 1
        assert valid[0] is sample_scalar_record
        assert errored[0] is malformed_record


# ---------------------------------------------------------------------------
# TestRules — unit tests for individual rules in ALL_RULES
# ---------------------------------------------------------------------------


def _apply_rules(record):
    """Helper: run ALL_RULES on a record, return list of (code, severity, message)."""
    results = []
    run_id = "test-run"
    for rule in ALL_RULES:
        issues = rule.apply(record, run_id)
        for issue in issues:
            results.append((issue.code, issue.severity, issue.message))
    return results


def _find_issues(record, code):
    """Helper: apply all rules and filter by code."""
    return [r for r in _apply_rules(record) if r[0] == code]


class TestRules:
    """Tests for individual validation rules."""

    def test_missing_id_flagged(self, malformed_record):
        hits = _find_issues(malformed_record, "MISSING_ID")
        assert len(hits) == 1
        assert hits[0][1] == "error"

    def test_missing_name_flagged(self, malformed_record):
        # malformed_record has name=None and name_en=None
        hits = _find_issues(malformed_record, "MISSING_NAME")
        assert len(hits) == 1
        assert hits[0][1] == "error"

    def test_missing_category_flagged(self, malformed_record):
        # malformed_record has category=""
        hits = _find_issues(malformed_record, "MISSING_CATEGORY")
        assert len(hits) == 1
        assert hits[0][1] == "error"

    def test_valid_record_no_issues(self, sample_scalar_record):
        # Fix category to one in VALID_CATEGORIES so no warnings fire
        sample_scalar_record.category = "physical"
        results = _apply_rules(sample_scalar_record)
        # A fully valid scalar record should produce zero issues
        assert len(results) == 0

    def test_invalid_value_type_flagged(self, sample_scalar_record):
        # Mutate value_type to something invalid
        sample_scalar_record.value_type = "banana"
        hits = _find_issues(sample_scalar_record, "INVALID_VALUE_TYPE")
        assert len(hits) == 1
        assert hits[0][1] == "error"
        assert "banana" in hits[0][2]

    def test_scalar_missing_value_flagged(self):
        from models import ExtractedRecord

        rec = ExtractedRecord(
            record_id="no-val-001",
            source_file="test.json",
            name="test",
            category="physical",
            value_type="scalar",
            value_scalar=None,
            raw_value=None,
        )
        hits = _find_issues(rec, "SCALAR_NO_VALUE")
        assert len(hits) == 1
        assert hits[0][1] == "error"
