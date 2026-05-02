"""Tests for extract module: extract_records, _to_extracted_record, _clean_source_file."""

import json
import pytest

from extract import extract_records, _to_extracted_record, _clean_source_file


# ========================================================================
# TestExtractRecords
# ========================================================================


class TestExtractRecords:
    """Tests for extract_records(source_dir) generator."""

    def test_extracts_valid_scalar_from_directory(self, tmp_path):
        """Valid JSON parameter files in the directory are parsed and yielded."""
        # Create a file in the "parameters" wrapper format that extract_records expects
        data = {
            "parameters": [
                {
                    "id": "json-scalar-001",
                    "name": "密度",
                    "name_en": "density",
                    "category": "physical_property",
                    "value_type": "scalar",
                    "value": 15.6,
                    "unit": "g/cm³",
                    "material": "U-10Zr",
                    "temperature_K": 293,
                }
            ]
        }
        f = tmp_path / "valid_param.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        records = list(extract_records(str(tmp_path)))

        assert len(records) == 1
        rec = records[0]
        assert rec.record_id == "json-scalar-001"
        assert rec.name == "密度"
        assert rec.name_en == "density"
        assert rec.category == "physical_property"
        assert rec.value_type == "scalar"
        assert rec.value_scalar == 15.6
        assert rec.raw_unit == "g/cm³"
        assert rec.raw_material == "U-10Zr"
        assert rec.temperature_K == 293.0

    def test_skips_malformed_json_gracefully(self, tmp_json_dir):
        """Malformed JSON files are skipped; valid files still extracted."""
        records = list(extract_records(str(tmp_json_dir)))

        # tmp_json_dir creates one valid file and one malformed file.
        # The valid file uses "records" wrapper, not "parameters",
        # so extract_records treats the wrapper dict as a single record.
        # The malformed file is skipped (logged as fatal, no crash).
        assert len(records) == 1

    def test_empty_directory_produces_no_records(self, tmp_path):
        """An empty directory yields no records."""
        records = list(extract_records(str(tmp_path)))
        assert records == []

    def test_nonexistent_directory_produces_no_records(self):
        """A non-existent directory yields no records without crashing."""
        records = list(extract_records("/no/such/directory/__nfmd_test__"))
        assert records == []


# ========================================================================
# TestToExtractedRecord
# ========================================================================


class TestToExtractedRecord:
    """Tests for _to_extracted_record(rec, filename)."""

    def test_full_record_maps_correctly(self):
        """All fields present in the input dict map to the correct attributes."""
        rec = {
            "id": "full-001",
            "source_file": "summaries/test.md",
            "source_paper": "Rest 1993",
            "name": "肿胀率",
            "name_en": "swelling_rate",
            "name_zh": "肿胀率",
            "symbol": "ΔV/V",
            "category": "irradiation_property",
            "subcategory": "swelling",
            "value_type": "scalar",
            "value": 2.5,
            "unit": "%",
            "material": "U-10Zr",
            "temperature_K": 600,
            "burnup_range": "1–10 at%",
            "method": "experiment",
            "confidence": "high",
            "equation": "E = mc^2",
            "notes": "Test note",
            "description": "A test description",
            "phase": "gamma",
            "conditions": "steady-state",
            "uncertainty": "±5%",
        }
        result = _to_extracted_record(rec, "fallback.json")

        assert result.record_id == "full-001"
        assert result.source_file == "test"  # summaries/ stripped, .md stripped
        assert result.source_paper == "Rest 1993"
        assert result.name == "肿胀率"
        assert result.name_en == "swelling_rate"
        assert result.name_zh == "肿胀率"
        assert result.symbol == "ΔV/V"
        assert result.category == "irradiation_property"
        assert result.subcategory == "swelling"
        assert result.value_type == "scalar"
        assert result.raw_value == 2.5
        assert result.raw_unit == "%"
        assert result.raw_material == "U-10Zr"
        assert result.raw_burnup == "1–10 at%"
        assert result.raw_method == "experiment"
        assert result.raw_confidence == "high"
        assert result.equation == "E = mc^2"
        assert result.notes == "Test note"
        assert result.description == "A test description"
        assert result.phase == "gamma"
        assert result.conditions == "steady-state"
        assert result.uncertainty == "±5%"
        assert result.value_scalar == 2.5
        assert result.temperature_K == 600.0

    def test_missing_optional_fields_default_to_none(self):
        """Optional fields not present in the input default to None."""
        rec = {
            "id": "minimal-001",
            "name": "密度",
            "category": "physical_property",
            "value_type": "scalar",
            "value": 15.6,
        }
        result = _to_extracted_record(rec, "minimal.json")

        assert result.record_id == "minimal-001"
        assert result.source_file == "minimal.json"
        assert result.source_paper is None
        assert result.name_en is None
        assert result.name_zh is None
        assert result.symbol is None
        assert result.subcategory is None
        assert result.raw_unit is None
        assert result.raw_material is None
        assert result.raw_temperature is None
        assert result.raw_burnup is None
        assert result.equation is None
        assert result.notes is None

    def test_string_value_converted_to_float(self):
        """A string 'value' field is parsed to float for scalar type."""
        rec = {
            "id": "str-001",
            "name": "密度",
            "category": "physical_property",
            "value_type": "scalar",
            "value": "42.5",
        }
        result = _to_extracted_record(rec, "str_val.json")
        assert result.value_scalar == 42.5

    def test_non_numeric_value_becomes_none(self):
        """A non-numeric string value produces None for value_scalar."""
        rec = {
            "id": "nan-001",
            "name": "密度",
            "category": "physical_property",
            "value_type": "scalar",
            "value": "not_a_number",
        }
        result = _to_extracted_record(rec, "nan_val.json")
        assert result.value_scalar is None


# ========================================================================
# TestCleanSourceFile
# ========================================================================


class TestCleanSourceFile:
    """Tests for _clean_source_file(source)."""

    def test_strips_leading_paths(self):
        """Path prefix 'summaries/' and '.md' extension are stripped."""
        assert _clean_source_file("summaries/x.json") == "x.json"

    def test_plain_filename_unchanged(self):
        """A plain filename without path prefix passes through unchanged."""
        assert _clean_source_file("x.json") == "x.json"

    def test_empty_string_returns_empty(self):
        """An empty string returns empty string."""
        assert _clean_source_file("") == ""
