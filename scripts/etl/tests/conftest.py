"""Shared pytest fixtures for NFMD ETL pipeline tests."""

import json
import os
import sys
import tempfile

import pytest

# Ensure scripts/etl/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ExtractedRecord


# ---------------------------------------------------------------------------
# Valid ExtractedRecord fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_scalar_record():
    """A valid scalar ExtractedRecord with a single numeric value."""
    return ExtractedRecord(
        record_id="test-scalar-001",
        source_file="scalar_test.json",
        source_paper="Test Paper 2024",
        name="密度",
        name_en="density",
        name_zh="密度",
        symbol="ρ",
        category="physical_property",
        subcategory="density",
        value_type="scalar",
        raw_value="15.6",
        raw_unit="g/cm³",
        raw_material="U-10Zr",
        raw_temperature="293",
        temperature_K=293.0,
        value_scalar=15.6,
    )


@pytest.fixture
def sample_range_record():
    """A valid range ExtractedRecord with min/max values."""
    return ExtractedRecord(
        record_id="test-range-001",
        source_file="range_test.json",
        source_paper="Test Paper 2024",
        name="热导率",
        name_en="thermal_conductivity",
        symbol="k",
        category="thermal_property",
        subcategory="conductivity",
        value_type="range",
        raw_value="10–25",
        raw_unit="W/(m·K)",
        raw_material="U-10Zr",
        raw_temperature="600–1000",
        value_min=10.0,
        value_max=25.0,
    )


@pytest.fixture
def sample_expression_record():
    """A valid expression ExtractedRecord with a LaTeX equation."""
    return ExtractedRecord(
        record_id="test-expr-001",
        source_file="expr_test.json",
        source_paper="Test Paper 2024",
        name="热膨胀系数",
        name_en="thermal_expansion_coefficient",
        symbol="α",
        category="thermal_property",
        subcategory="expansion",
        value_type="expression",
        raw_value="\\alpha = 1.2 \\times 10^{-5} + 5.3 \\times 10^{-9} T",
        raw_unit="1/K",
        raw_material="U-10Zr",
        raw_temperature="300–1200 K",
        value_expr="\\alpha = 1.2e-5 + 5.3e-9 * T",
        equation="\\alpha = 1.2 \\times 10^{-5} + 5.3 \\times 10^{-9} T",
    )


@pytest.fixture
def sample_list_record():
    """A valid list ExtractedRecord with an array of values."""
    return ExtractedRecord(
        record_id="test-list-001",
        source_file="list_test.json",
        source_paper="Test Paper 2024",
        name="辐照肿胀率",
        name_en="swelling_rate",
        category="irradiation_property",
        subcategory="swelling",
        value_type="list",
        raw_value="[0.5, 1.2, 2.8, 4.1]",
        raw_unit="%/at%",
        raw_material="U-10Zr",
        raw_burnup="1–10 at%",
        value_list=[0.5, 1.2, 2.8, 4.1],
    )


# ---------------------------------------------------------------------------
# Malformed / edge-case fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def malformed_record():
    """An ExtractedRecord with empty required fields for validation tests."""
    return ExtractedRecord(
        record_id="",
        source_file="bad_data.json",
        name=None,          # type: ignore  — intentionally wrong
        category="",
        value_type="scalar",
        raw_value=None,
    )


# ---------------------------------------------------------------------------
# File-system fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_json_dir(tmp_path):
    """Temp directory with a valid JSON parameter file and a malformed one."""
    valid = {
        "metadata": {"paper": "Test Paper 2024", "doi": "10.1234/test"},
        "records": [
            {
                "record_id": "json-scalar-001",
                "name": "密度",
                "name_en": "density",
                "category": "physical_property",
                "value_type": "scalar",
                "value": 15.6,
                "unit": "g/cm³",
                "material": "U-10Zr",
                "temperature_K": 293,
            }
        ],
    }
    valid_path = tmp_path / "valid_param.json"
    valid_path.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{not valid json !!", encoding="utf-8")

    return tmp_path


@pytest.fixture
def tmp_jsonl_file(tmp_path):
    """Temp JSONL file path for I/O tests (file is created empty)."""
    p = tmp_path / "output.jsonl"
    p.touch()
    return str(p)
