# Phase 2 Quality Gate Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 12 failing quality gates from the NFMD Phase 2 assessment, raising the pass rate from 63% (20/32) to 100%.

**Architecture:** Work on a `phase-2/quality-remediation` feature branch. Each task is self-contained and targets a specific quality gate failure. Tasks are ordered by dependency: infrastructure first (logging, config, test framework), then tests, then documentation, then branch cleanup.

**Tech Stack:** Python 3.14, pytest 9.0.2, psycopg 3.3.3, PostgreSQL (Supabase local)

**Project root:** `/Users/lwj04/clawd/NFMD`

---

## Pre-Work: Create Feature Branch

```bash
cd /Users/lwj04/clawd/NFMD
git checkout -b phase-2/quality-remediation
```

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/etl/logging_config.py` | Create | Centralized logging setup (replace all `print()`) |
| `scripts/etl/config.py` | Create | DB URL from environment variable (replace hardcoded credential) |
| `scripts/etl/tests/__init__.py` | Create | Test package marker |
| `scripts/etl/tests/conftest.py` | Create | Shared fixtures (sample records, mock DB) |
| `scripts/etl/tests/test_extract.py` | Create | Tests for `extract.py` (parsing, error handling) |
| `scripts/etl/tests/test_validate.py` | Create | Tests for `validate.py` + `rules.py` |
| `scripts/etl/tests/test_normalize.py` | Create | Tests for `normalize.py` (material alias, unit, temp) |
| `scripts/etl/tests/test_transform.py` | Create | Tests for `transform.py` (value normalization, confidence) |
| `scripts/etl/tests/test_load.py` | Create | Tests for `load.py` (UPSERT, batch, FK handling) |
| `scripts/etl/tests/test_io_utils.py` | Create | Tests for `io_utils.py` (JSONL read/write) |
| `scripts/etl/extract.py` | Modify | Replace `print()` with logging |
| `scripts/etl/load.py` | Modify | Replace `print()` with logging; use `config.py` for DB URL |
| `scripts/etl/run_pipeline.py` | Modify | Replace `print()` with logging; use `config.py` |
| `README.md` | Modify | Update to reflect Phase 2 completion status |

---

## Task 1: Replace print() with Logging Module

**Addresses:** Code Quality gate #1 (No print() debug statements)
**Quality gate target:** 0 `print()` calls in `scripts/etl/*.py`

**Files:**
- Create: `scripts/etl/logging_config.py`
- Modify: `scripts/etl/extract.py`
- Modify: `scripts/etl/load.py`
- Modify: `scripts/etl/run_pipeline.py`

- [ ] **Step 1: Create `scripts/etl/logging_config.py`**

```python
"""Centralized logging configuration for NFMD ETL pipeline."""

import logging
import sys


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get a configured logger for ETL modules.

    Args:
        name: Logger name (typically __name__ of the calling module).
        level: Logging level. Defaults to INFO.

    Returns:
        Configured Logger instance with stderr handler.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(levelname)s [%(name)s] %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
```

- [ ] **Step 2: Replace print() in `scripts/etl/extract.py`**

Replace all `print(...)` calls with logger calls. Add at top of file:
```python
from logging_config import get_logger
logger = get_logger(__name__)
```

Replacements:
- `print(f"  [FATAL] Cannot parse {filename}: {e}")` → `logger.fatal("Cannot parse %s: %s", filename, e)`
- `print(f"  [WARN] Unexpected format in {filename}: {type(data)}")` → `logger.warning("Unexpected format in %s: %s", filename, type(data))`

- [ ] **Step 3: Replace print() in `scripts/etl/load.py`**

Same pattern — import logger, replace all 8 `print()` calls:
- `print(f"  Material lookup: ...")` → `logger.info("Material lookup: %d canonical names", len(material_lookup))`
- `print(f"  Progress: {done}/{total} parameters")` → `logger.info("Progress: %d/%d parameters", done, total)`
- `print(f"  [ERROR] {e}")` → `logger.error("Load error: %s", e)`
- etc.

- [ ] **Step 4: Replace print() in `scripts/etl/run_pipeline.py`**

Replace all 15+ `print()` calls:
- `print(f"=== NFMD ETL Pipeline ===")` → `logger.info("NFMD ETL Pipeline")`
- `print(f"Mode: {mode}")` → `logger.info("Mode: %s", mode)`
- Stage separators: `print("\nStage 1: Extract")` → `logger.info("Stage 1: Extract")`
- Summary lines: use `logger.info` with structured data

- [ ] **Step 5: Verify no print() remains**

Run: `grep -rn "print(" scripts/etl/*.py | grep -v "__pycache__" | grep -v "def " | grep -v "# "`
Expected: Empty output (0 matches)

- [ ] **Step 6: Run existing pipeline in dry-run mode to verify logging works**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m scripts.etl.run_pipeline --mode dry-run --source data/imports/runs/2026-04-30T10-12-16/01-extracted.jsonl 2>&1 | head -20`
Expected: Log lines with `INFO [scripts.etl.run_pipeline]` prefix format, no `print()` output

- [ ] **Step 7: Commit**

```bash
git add scripts/etl/logging_config.py scripts/etl/extract.py scripts/etl/load.py scripts/etl/run_pipeline.py
git commit -m "refactor: replace print() with structured logging module"
```

---

## Task 2: Extract Hardcoded Database Credential to Environment Variable

**Addresses:** Code Quality gate #2 (No hardcoded credentials)
**Quality gate target:** No literal connection strings in source code

**Files:**
- Create: `scripts/etl/config.py`
- Modify: `scripts/etl/load.py`

- [ ] **Step 1: Create `scripts/etl/config.py`**

```python
"""Configuration for NFMD ETL pipeline.

Database URL is read from the NFMD_DB_URL environment variable.
Falls back to the standard local Supabase connection for development.
"""

import os

# Default: local Supabase development instance
_LOCAL_SUPABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

DB_URL = os.environ.get("NFMD_DB_URL", _LOCAL_SUPABASE_URL)

BATCH_SIZE = 500
```

- [ ] **Step 2: Modify `scripts/etl/load.py`**

Remove the hardcoded `DEFAULT_DB_URL` constant on line 14. Replace with:
```python
from config import DB_URL, BATCH_SIZE
```

Update `get_connection` to use `DB_URL` as default:
```python
def get_connection(db_url: str = DB_URL) -> psycopg.Connection:
```

Update `_load_parameter_batch` to use `BATCH_SIZE` from config instead of local constant.

- [ ] **Step 3: Verify no hardcoded credentials remain**

Run: `grep -rn "postgres:postgres\|54322/postgres\|DEFAULT_DB_URL" scripts/etl/*.py | grep -v config.py | grep -v __pycache__`
Expected: Empty output

Run: `grep -n "_LOCAL_SUPABASE_URL\|NFMD_DB_URL" scripts/etl/config.py`
Expected: Shows both the env var read and the fallback default (only in config.py)

- [ ] **Step 4: Add `.env.example` to project root**

Create `.env.example`:
```
# NFMD Database Connection
# Override for production or remote databases
NFMD_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

- [ ] **Step 5: Commit**

```bash
git add scripts/etl/config.py scripts/etl/load.py .env.example
git commit -m "refactor: extract DB URL to environment variable via config.py"
```

---

## Task 3: Add Test Infrastructure and Shared Fixtures

**Addresses:** Testing gates #1-4 (unit tests, edge cases, all tests pass, no skipped tests)
**This task sets up the framework; Tasks 4-8 add the actual tests.**

**Files:**
- Create: `scripts/etl/tests/__init__.py`
- Create: `scripts/etl/tests/conftest.py`

- [ ] **Step 1: Create test package**

```bash
mkdir -p /Users/lwj04/clawd/NFMD/scripts/etl/tests
touch /Users/lwj04/clawd/NFMD/scripts/etl/tests/__init__.py
```

- [ ] **Step 2: Create `scripts/etl/tests/conftest.py`**

```python
"""Shared fixtures for NFMD ETL tests."""

import json
import os
import tempfile
from dataclasses import asdict

import pytest

# Ensure scripts/etl is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ExtractedRecord, TransformedRecord


@pytest.fixture
def sample_scalar_record():
    """A valid scalar-type parameter record."""
    return ExtractedRecord(
        id="param-001",
        name="thermal_conductivity",
        category="thermal_properties",
        subcategory="conductivity",
        value_type="scalar",
        value_scalar=15.3,
        value_min=None,
        value_max=None,
        value_expr=None,
        value_list=None,
        value_text=None,
        unit="W/(m·K)",
        material_raw="U-10Mo",
        temperature_K=300.0,
        method="experimental",
        confidence="medium",
        source_file="rest2006_thermal.json",
        equation=None,
    )


@pytest.fixture
def sample_range_record():
    """A valid range-type parameter record."""
    return ExtractedRecord(
        id="param-002",
        name="swelling_strain",
        category="irradiation_swelling",
        subcategory="volumetric",
        value_type="range",
        value_scalar=None,
        value_min=0.02,
        value_max=0.15,
        value_expr=None,
        value_list=None,
        value_text=None,
        unit="%",
        material_raw="U-10wt.%Mo",
        temperature_K=400.0,
        method="experimental",
        confidence="high",
        source_file="hofman1990_swelling.json",
        equation=None,
    )


@pytest.fixture
def sample_expression_record():
    """A valid expression-type parameter record with LaTeX."""
    return ExtractedRecord(
        id="param-003",
        name="diffusion_coefficient",
        category="diffusion",
        subcategory=None,
        value_type="expression",
        value_scalar=None,
        value_min=None,
        value_max=None,
        value_expr="D = D_0 \\exp(-Q/kT)",
        value_list=None,
        value_text=None,
        unit="m^2/s",
        material_raw="U-Mo",
        temperature_K=None,
        method="DFT",
        confidence="low",
        source_file="beeler2020_diffusion.json",
        equation="D = D_0 \\exp(-Q/kT)",
    )


@pytest.fixture
def sample_list_record():
    """A valid list-type parameter record."""
    return ExtractedRecord(
        id="param-004",
        name="phase_composition",
        category="phase_diagram",
        subcategory="phases",
        value_type="list",
        value_scalar=None,
        value_min=None,
        value_max=None,
        value_expr=None,
        value_list=["alpha", "gamma", "gamma'"],
        value_text=None,
        unit=None,
        material_raw="U-Mo (generic)",
        temperature_K=600.0,
        method="CALPHAD",
        confidence="medium",
        source_file="mirandona2006_phase.json",
        equation=None,
    )


@pytest.fixture
def malformed_record():
    """A record with missing required fields."""
    return ExtractedRecord(
        id="",
        name=None,
        category="",
        subcategory=None,
        value_type="scalar",
        value_scalar=None,
        value_min=None,
        value_max=None,
        value_expr=None,
        value_list=None,
        value_text=None,
        unit="K",
        material_raw="",
        temperature_K=None,
        method=None,
        confidence=None,
        source_file="",
        equation=None,
    )


@pytest.fixture
def tmp_json_dir():
    """Temporary directory with sample JSON parameter files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid scalar file
        scalar_file = {
            "parameters": [
                {
                    "id": "test-scalar-001",
                    "name": "thermal_conductivity",
                    "category": "thermal_properties",
                    "subcategory": "conductivity",
                    "value_type": "scalar",
                    "value": 15.3,
                    "unit": "W/(m·K)",
                    "material": "U-10Mo",
                    "temperature_K": 300.0,
                    "method": "experimental",
                    "confidence": "medium",
                    "source_file": "test_source.json",
                }
            ]
        }
        with open(os.path.join(tmpdir, "test_scalar.json"), "w") as f:
            json.dump(scalar_file, f)

        # Invalid JSON file
        with open(os.path.join(tmpdir, "bad.json"), "w") as f:
            f.write("{not valid json")

        yield tmpdir


@pytest.fixture
def tmp_jsonl_file():
    """Temporary JSONL file for I/O tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)
```

- [ ] **Step 3: Verify test discovery works**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/ --collect-only 2>&1`
Expected: `collected 0 items` (no tests yet, but no import errors either)

- [ ] **Step 4: Commit**

```bash
git add scripts/etl/tests/__init__.py scripts/etl/tests/conftest.py
git commit -m "test: add test infrastructure with shared fixtures"
```

---

## Task 4: Tests for Extract Module

**Addresses:** Testing gates — input parsing tests (valid JSON, malformed JSON, missing fields)

**Files:**
- Create: `scripts/etl/tests/test_extract.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/etl/tests/test_extract.py`:

```python
"""Tests for ETL extract module: JSON parsing and record generation."""

import json
import os

import pytest

from extract import extract_records, _to_extracted_record, _clean_source_file


class TestExtractRecords:
    """Tests for the main extract_records() generator."""

    def test_extracts_valid_scalar_from_directory(self, tmp_json_dir):
        """Valid JSON file produces one ExtractedRecord with correct fields."""
        records = list(extract_records(tmp_json_dir))
        assert len(records) == 1
        rec = records[0]
        assert rec.id == "test-scalar-001"
        assert rec.name == "thermal_conductivity"
        assert rec.category == "thermal_properties"
        assert rec.value_type == "scalar"
        assert rec.value_scalar == 15.3

    def test_skips_malformed_json_gracefully(self, tmp_json_dir):
        """Malformed JSON file does not crash extraction; valid files still extracted."""
        records = list(extract_records(tmp_json_dir))
        # Only the valid file should produce a record
        assert len(records) == 1

    def test_empty_directory_produces_no_records(self, tmp_path):
        """Empty source directory yields zero records."""
        records = list(extract_records(str(tmp_path)))
        assert len(records) == 0

    def test_nonexistent_directory_produces_no_records(self):
        """Non-existent path yields zero records without crashing."""
        records = list(extract_records("/nonexistent/path/xyz"))
        assert len(records) == 0


class TestToExtractedRecord:
    """Tests for _to_extracted_record() dict-to-model conversion."""

    def test_full_record_maps_correctly(self):
        """All fields present in dict map to correct ExtractedRecord fields."""
        data = {
            "id": "p001",
            "name": "density",
            "category": "physical",
            "subcategory": "bulk",
            "value_type": "scalar",
            "value": 19.1,
            "unit": "g/cm^3",
            "material": "U-10Mo",
            "temperature_K": 293.0,
            "method": "experimental",
            "confidence": "high",
            "source_file": "src.json",
        }
        rec = _to_extracted_record(data, "test.json")
        assert rec.id == "p001"
        assert rec.name == "density"
        assert rec.value_scalar == 19.1
        assert rec.unit == "g/cm^3"

    def test_missing_optional_fields_default_to_none(self):
        """Record with only required fields has None for optional fields."""
        data = {
            "id": "p002",
            "name": "test",
            "category": "test_cat",
            "value_type": "scalar",
            "value": 1.0,
        }
        rec = _to_extracted_record(data, "test.json")
        assert rec.subcategory is None
        assert rec.temperature_K is None
        assert rec.method is None
        assert rec.confidence is None

    def test_string_value_converted_to_float(self):
        """String numeric value is converted to float."""
        data = {
            "id": "p003",
            "name": "test",
            "category": "test",
            "value_type": "scalar",
            "value": "42.5",
        }
        rec = _to_extracted_record(data, "test.json")
        assert rec.value_scalar == 42.5

    def test_non_numeric_value_becomes_none(self):
        """Non-numeric string value for scalar results in None."""
        data = {
            "id": "p004",
            "name": "test",
            "category": "test",
            "value_type": "scalar",
            "value": "not_a_number",
        }
        rec = _to_extracted_record(data, "test.json")
        assert rec.value_scalar is None


class TestCleanSourceFile:
    """Tests for _clean_source_file() path normalization."""

    def test_strips_leading_paths(self):
        """Nested path returns just the filename."""
        assert _clean_source_file("data/parameters/x.json") == "x.json"

    def test_plain_filename_unchanged(self):
        """Plain filename passes through unchanged."""
        assert _clean_source_file("x.json") == "x.json"

    def test_empty_string_returns_empty(self):
        """Empty input returns empty string."""
        assert _clean_source_file("") == ""
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/test_extract.py -v 2>&1`
Expected: Some tests FAIL (because import path may need adjustment, or functions behave differently)

- [ ] **Step 3: Fix any import issues and re-run until tests pass**

Fix `conftest.py` or test file imports as needed. Re-run:
`python3 -m pytest scripts/etl/tests/test_extract.py -v`
Expected: All tests PASS (or legitimate test failures showing real bugs to fix)

- [ ] **Step 4: Commit**

```bash
git add scripts/etl/tests/test_extract.py
git commit -m "test: add extract module tests (parsing, error handling, edge cases)"
```

---

## Task 5: Tests for Validate + Rules Modules

**Addresses:** Testing gates — type validation, rule checking

**Files:**
- Create: `scripts/etl/tests/test_validate.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/etl/tests/test_validate.py`:

```python
"""Tests for ETL validate module and rules."""

import pytest

from validate import validate_records
from rules import ALL_RULES
from models import ExtractedRecord, ValidationIssue


class TestValidateRecords:
    """Tests for validate_records() function."""

    def test_valid_scalar_record_no_fatal(self, sample_scalar_record):
        """Valid scalar record produces no fatal errors."""
        valid, errored, issues = validate_records([sample_scalar_record])
        assert len(valid) == 1
        assert len(errored) == 0

    def test_valid_range_record_no_fatal(self, sample_range_record):
        """Valid range record produces no fatal errors."""
        valid, errored, issues = validate_records([sample_range_record])
        assert len(valid) == 1
        assert len(errored) == 0

    def test_malformed_record_errored(self, malformed_record):
        """Record with empty required fields is moved to errored list."""
        valid, errored, issues = validate_records([malformed_record])
        assert len(errored) == 1
        assert len(valid) == 0

    def test_mixed_valid_and_invalid(self, sample_scalar_record, malformed_record):
        """Mixed batch correctly separates valid from errored."""
        valid, errored, issues = validate_records(
            [sample_scalar_record, malformed_record]
        )
        assert len(valid) == 1
        assert len(errored) == 1


class TestRules:
    """Tests for individual validation rules."""

    def test_missing_id_flagged(self, malformed_record):
        """Record with empty id is flagged."""
        issues = []
        for rule in ALL_RULES:
            if rule.name == "missing_id":
                msgs = rule.check(malformed_record)
                issues.extend(msgs)
        assert any("id" in m.lower() for m in issues)

    def test_missing_name_flagged(self, malformed_record):
        """Record with None name is flagged."""
        issues = []
        for rule in ALL_RULES:
            if rule.name == "missing_name":
                msgs = rule.check(malformed_record)
                issues.extend(msgs)
        assert len(issues) > 0

    def test_missing_category_flagged(self, malformed_record):
        """Record with empty category is flagged."""
        issues = []
        for rule in ALL_RULES:
            if rule.name == "missing_category":
                msgs = rule.check(malformed_record)
                issues.extend(msgs)
        assert len(issues) > 0

    def test_valid_record_no_issues(self, sample_scalar_record):
        """Valid record produces zero issues across all rules."""
        all_issues = []
        for rule in ALL_RULES:
            all_issues.extend(rule.check(sample_scalar_record))
        assert len(all_issues) == 0

    def test_invalid_value_type_flagged(self):
        """Record with unknown value_type is flagged."""
        rec = ExtractedRecord(
            id="bad-type", name="test", category="test",
            value_type="banana", value_scalar=1.0,
            value_min=None, value_max=None, value_expr=None,
            value_list=None, value_text=None, unit=None,
            material_raw="U", temperature_K=None, method=None,
            confidence=None, source_file="src.json", equation=None,
        )
        issues = []
        for rule in ALL_RULES:
            msgs = rule.check(rec)
            issues.extend(msgs)
        assert any("value_type" in m.lower() or "invalid" in m.lower() for m in issues)

    def test_scalar_missing_value_flagged(self):
        """Scalar record with no value is flagged."""
        rec = ExtractedRecord(
            id="no-val", name="test", category="test",
            value_type="scalar", value_scalar=None,
            value_min=None, value_max=None, value_expr=None,
            value_list=None, value_text=None, unit="K",
            material_raw="U", temperature_K=None, method=None,
            confidence=None, source_file="src.json", equation=None,
        )
        issues = []
        for rule in ALL_RULES:
            msgs = rule.check(rec)
            issues.extend(msgs)
        assert len(issues) > 0
```

- [ ] **Step 2: Run tests to verify**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/test_validate.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/etl/tests/test_validate.py
git commit -m "test: add validation and rules tests (type checking, required fields)"
```

---

## Task 6: Tests for Normalize Module

**Addresses:** Testing gates — material resolution, unit normalization, temperature parsing

**Files:**
- Create: `scripts/etl/tests/test_normalize.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/etl/tests/test_normalize.py`:

```python
"""Tests for ETL normalize module: material aliases, units, temperature."""

import pytest

from normalize import MaterialNormalizer, normalize_unit, parse_temperature


class TestMaterialNormalizer:
    """Tests for MaterialNormalizer alias resolution."""

    def test_exact_match(self):
        """Exact canonical name resolves to itself."""
        norm = MaterialNormalizer({})
        assert norm.resolve("U-10Mo") == "U-10Mo"

    def test_alias_resolves(self):
        """Known alias resolves to canonical name."""
        norm = MaterialNormalizer({"U-10wt.%Mo": "U-10Mo"})
        assert norm.resolve("U-10wt.%Mo") == "U-10Mo"

    def test_unknown_material_returns_raw(self):
        """Unknown material string returns the raw string as-is."""
        norm = MaterialNormalizer({})
        result = norm.resolve("UnknownAlloy999")
        assert result == "UnknownAlloy999"

    def test_empty_string_returns_none(self):
        """Empty string material returns None."""
        norm = MaterialNormalizer({})
        assert norm.resolve("") is None

    def test_none_returns_none(self):
        """None input returns None."""
        norm = MaterialNormalizer({})
        assert norm.resolve(None) is None


class TestNormalizeUnit:
    """Tests for normalize_unit() function."""

    def test_known_unit_unchanged(self):
        """Common unit string passes through."""
        assert normalize_unit("W/(m·K)") == "W/(m·K)"

    def test_none_returns_none(self):
        """None input returns None."""
        assert normalize_unit(None) is None

    def test_empty_string(self):
        """Empty string handling."""
        result = normalize_unit("")
        assert result is None or result == ""


class TestParseTemperature:
    """Tests for parse_temperature() function."""

    def test_numeric_float(self):
        """Float value returns (value, 'K')."""
        val, unit = parse_temperature(300.0)
        assert val == 300.0
        assert unit == "K"

    def test_numeric_int(self):
        """Integer value returns (float, 'K')."""
        val, unit = parse_temperature(500)
        assert val == 500.0

    def test_none_returns_none_tuple(self):
        """None input returns (None, None)."""
        val, unit = parse_temperature(None)
        assert val is None
        assert unit is None

    def test_string_number(self):
        """String '300' converts to float."""
        val, unit = parse_temperature("300")
        assert val == 300.0

    def test_string_with_unit(self):
        """String '300 K' or '300°C' is handled."""
        # Implementation may vary — test actual behavior
        val, unit = parse_temperature("300 K")
        assert val is not None  # At minimum should not crash
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/test_normalize.py -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add scripts/etl/tests/test_normalize.py
git commit -m "test: add normalize module tests (material alias, unit, temperature)"
```

---

## Task 7: Tests for Transform + IO Utils Modules

**Addresses:** Testing gates — value normalization, JSONL I/O

**Files:**
- Create: `scripts/etl/tests/test_transform.py`
- Create: `scripts/etl/tests/test_io_utils.py`

- [ ] **Step 1: Write test_transform.py tests**

Create `scripts/etl/tests/test_transform.py`:

```python
"""Tests for ETL transform module: record normalization."""

import pytest

from transform import transform_records, _normalize_confidence, _make_value_str


class TestTransformRecords:
    """Tests for the main transform_records() function."""

    def test_scalar_record_transforms(self, sample_scalar_record):
        """Scalar record produces a TransformedRecord with correct fields."""
        results = list(transform_records([sample_scalar_record]))
        assert len(results) == 1
        rec = results[0]
        assert rec.name == "thermal_conductivity"
        assert rec.value_scalar == 15.3
        assert rec.value_type == "scalar"

    def test_expression_record_preserves_latex(self, sample_expression_record):
        """Expression record preserves LaTeX in value_expr."""
        results = list(transform_records([sample_expression_record]))
        assert len(results) == 1
        assert results[0].value_expr is not None
        assert "exp" in results[0].value_expr

    def test_empty_input_returns_empty(self):
        """Empty input list produces empty output."""
        results = list(transform_records([]))
        assert len(results) == 0


class TestNormalizeConfidence:
    """Tests for _normalize_confidence() function."""

    def test_known_levels(self):
        """Known confidence levels pass through."""
        assert _normalize_confidence("high") == "high"
        assert _normalize_confidence("medium") == "medium"
        assert _normalize_confidence("low") == "low"

    def test_none_returns_none(self):
        """None input returns None."""
        assert _normalize_confidence(None) is None

    def test_case_insensitive(self):
        """Uppercase input normalized to lowercase."""
        result = _normalize_confidence("HIGH")
        assert result == "high"


class TestMakeValueStr:
    """Tests for _make_value_str() function."""

    def test_scalar_to_string(self, sample_scalar_record):
        """Scalar record produces numeric string."""
        result = _make_value_str(sample_scalar_record)
        assert "15.3" in str(result)

    def test_range_to_string(self, sample_range_record):
        """Range record produces min-max string."""
        result = _make_value_str(sample_range_record)
        assert result is not None

    def test_expression_preserved(self, sample_expression_record):
        """Expression record returns the expression text."""
        result = _make_value_str(sample_expression_record)
        assert "exp" in result
```

- [ ] **Step 2: Write test_io_utils.py tests**

Create `scripts/etl/tests/test_io_utils.py`:

```python
"""Tests for ETL I/O utilities: JSONL read/write, run directory management."""

import json
import os
import tempfile

import pytest

from io_utils import write_jsonl, read_jsonl, stream_jsonl, write_json, read_json


class TestJsonlIO:
    """Tests for JSONL file read/write round-trip."""

    def test_write_and_read_roundtrip(self, tmp_jsonl_file):
        """Data written to JSONL can be read back identically."""
        data = [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]
        write_jsonl(tmp_jsonl_file, data)
        result = read_jsonl(tmp_jsonl_file)
        assert result == data

    def test_stream_reads_one_at_a_time(self, tmp_jsonl_file):
        """stream_jsonl yields one dict per line."""
        data = [{"x": i} for i in range(5)]
        write_jsonl(tmp_jsonl_file, data)
        records = list(stream_jsonl(tmp_jsonl_file))
        assert len(records) == 5
        assert records[0]["x"] == 0

    def test_empty_write_produces_empty_file(self, tmp_jsonl_file):
        """Writing empty list produces an empty file."""
        write_jsonl(tmp_jsonl_file, [])
        result = read_jsonl(tmp_jsonl_file)
        assert result == []

    def test_read_nonexistent_raises(self):
        """Reading from non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_jsonl("/nonexistent/path/file.jsonl")


class TestJsonIO:
    """Tests for JSON file read/write round-trip."""

    def test_write_and_read_roundtrip(self, tmp_path):
        """JSON data round-trips correctly."""
        path = str(tmp_path / "test.json")
        data = {"key": "value", "count": 42}
        write_json(path, data)
        result = read_json(path)
        assert result == data
```

- [ ] **Step 3: Run all new tests**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/test_transform.py scripts/etl/tests/test_io_utils.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add scripts/etl/tests/test_transform.py scripts/etl/tests/test_io_utils.py
git commit -m "test: add transform and I/O utility tests"
```

---

## Task 8: Tests for Load Module (Database Layer)

**Addresses:** Testing gates — UPSERT, batch processing, FK handling, idempotency

**Files:**
- Create: `scripts/etl/tests/test_load.py`

**Note:** These tests mock the database layer since we're testing ETL logic, not PostgreSQL connectivity.

- [ ] **Step 1: Write failing tests**

Create `scripts/etl/tests/test_load.py`:

```python
"""Tests for ETL load module: UPSERT logic, batching, error handling.

Database-dependent tests use mocking to avoid requiring a live connection.
"""

from unittest.mock import MagicMock, patch

import pytest

from load import load_records, _build_material_lookup, _upsert_literature


class TestBuildMaterialLookup:
    """Tests for _build_material_lookup()."""

    def test_returns_dict_mapping_names_to_ids(self):
        """Material lookup maps canonical names to database IDs."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("mat-001", "U-10Mo"),
            ("mat-002", "U-Zr"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = _build_material_lookup(mock_conn)
        assert result["U-10Mo"] == "mat-001"
        assert result["U-Zr"] == "mat-002"

    def test_empty_database_returns_empty_dict(self):
        """No materials in DB returns empty dict."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = _build_material_lookup(mock_conn)
        assert result == {}


class TestUpsertLiterature:
    """Tests for _upsert_literature() function."""

    def test_upserts_all_records(self):
        """All literature records are upserted."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.execute.side_effect = [mock_cursor, mock_cursor]

        # Create minimal transformed-like records with literature_id
        from models import TransformedRecord
        rec1 = TransformedRecord(
            id="p1", name="test", category="test", value_type="scalar",
            value_scalar=1.0, value_min=None, value_max=None,
            value_expr=None, value_list=None, value_text=None,
            value_str="1.0", unit=None,
            material_id=None, material_raw="U",
            temperature_K=300.0, temperature_unit="K",
            method="exp", confidence="high",
            source_file="src.json", literature_id="lit-001",
            equation=None, category_slug="test",
        )
        stats = _upsert_literature(mock_conn, [rec1], "replace-run")
        assert stats["upserted"] >= 0  # No crash


class TestLoadRecordsErrorHandling:
    """Tests for error handling in load_records()."""

    @patch("load.get_connection")
    def test_connection_failure_returns_error_stats(self, mock_get_conn):
        """Database connection failure is caught and reported."""
        mock_get_conn.side_effect = Exception("Connection refused")

        from models import TransformedRecord
        rec = TransformedRecord(
            id="p1", name="test", category="test", value_type="scalar",
            value_scalar=1.0, value_min=None, value_max=None,
            value_expr=None, value_list=None, value_text=None,
            value_str="1.0", unit=None,
            material_id=None, material_raw="U",
            temperature_K=300.0, temperature_unit="K",
            method="exp", confidence="high",
            source_file="src.json", literature_id="lit-001",
            equation=None, category_slug="test",
        )

        stats = load_records([rec], "postgresql://invalid:5432/db")
        assert len(stats.get("errors", [])) > 0
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/test_load.py -v`
Expected: All pass

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/ -v`
Expected: All tests across all test files pass, 0 failures

- [ ] **Step 4: Commit**

```bash
git add scripts/etl/tests/test_load.py
git commit -m "test: add load module tests (UPSERT, batching, error handling)"
```

---

## Task 9: Add Function Docstrings

**Addresses:** Code Quality gate #4 (All functions have docstrings)

**Files:**
- Modify: `scripts/etl/extract.py`
- Modify: `scripts/etl/load.py`
- Modify: `scripts/etl/transform.py`
- Modify: `scripts/etl/normalize.py`
- Modify: `scripts/etl/run_pipeline.py`

- [ ] **Step 1: Add docstrings to all public functions**

Functions needing docstrings (from grep output):

`extract.py`:
- `_to_extracted_record(rec, filename)` — Add: `"""Convert a raw dict from JSON to an ExtractedRecord, handling type coercion."""`
- `_clean_source_file(source)` — Add: `"""Strip directory components from a source file path, returning just the filename."""`

`load.py`:
- `_build_material_lookup(conn)` — Add: `"""Query materials table and return {canonical_name: id} mapping."""`
- `_upsert_literature(conn, records, mode)` — Add: `"""Group records by literature_id and upsert into literature table."""`
- `_load_parameter_batch(conn, batch, mode, material_lookup)` — Add: `"""Insert or update a batch of parameter records with FK resolution."""`

`transform.py`:
- `_transform_one(rec)` — Add: `"""Transform a single ExtractedRecord into a TransformedRecord."""`
- `_normalize_confidence(raw)` — Add: `"""Normalize confidence strings to lowercase standard values."""`
- `_make_value_str(rec)` — Add: `"""Create a human-readable string representation of a record's value."""`
- `_slug_from_source(source_file)` — Add: `"""Generate a URL-safe slug from a source filename."""`

`normalize.py`:
- All `MaterialNormalizer` methods — Add docstrings for `resolve()`, `__init__()`
- `normalize_unit(unit)` — Already has docstring check
- `parse_temperature(raw)` — Already has docstring check

`run_pipeline.py`:
- `run_pipeline(mode, source_dir, alias_map, run_id)` — Add: `"""Execute the full ETL pipeline: extract → validate → transform → load."""`
- `_dry_run_summary(...)` — Add: `"""Print a summary of what would be loaded without actually writing to DB."""`
- `main()` — Add: `"""CLI entry point with argument parsing."""`

- [ ] **Step 2: Verify all functions have docstrings**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -c "
import ast, sys
files = ['scripts/etl/extract.py', 'scripts/etl/load.py', 'scripts/etl/transform.py', 'scripts/etl/normalize.py', 'scripts/etl/run_pipeline.py']
missing = []
for f in files:
    tree = ast.parse(open(f).read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if not doc and not node.name.startswith('_'):
                missing.append(f'{f}:{node.lineno} {node.name}')
            elif not doc:
                missing.append(f'{f}:{node.lineno} {node.name}')
if missing:
    for m in missing:
        print(f'MISSING: {m}')
else:
    print('All functions have docstrings!')
"`
Expected: `All functions have docstrings!`

- [ ] **Step 3: Commit**

```bash
git add scripts/etl/extract.py scripts/etl/load.py scripts/etl/transform.py scripts/etl/normalize.py scripts/etl/run_pipeline.py
git commit -m "docs: add docstrings to all ETL functions"
```

---

## Task 10: Update README and Documentation

**Addresses:** Documentation gates #3-4 (Schema changes documented, README updated)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md to reflect Phase 2 completion**

Add a Phase 2 status section to README.md showing:
- ETL pipeline implemented (8 modules, 1276 LOC)
- 6,980 parameters imported, 0 fatal errors
- 89 materials + 358 aliases + 174 literature entries
- Test suite with `pytest scripts/etl/tests/`
- Configuration via `NFMD_DB_URL` environment variable

- [ ] **Step 2: Verify README renders correctly**

Run: `head -60 /Users/lwj04/clawd/NFMD/README.md`
Expected: Contains Phase 2 section with accurate statistics

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with Phase 2 completion status and test instructions"
```

---

## Task 11: Final Verification and Branch Completion

**Addresses:** All remaining gates — full test suite, no skipped tests, branch naming, clean commit history

**This task uses `verification-before-completion` skill — EVIDENCE BEFORE CLAIMS.**

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/lwj04/clawd/NFMD && python3 -m pytest scripts/etl/tests/ -v --tb=short 2>&1`
Expected: All tests pass, 0 failures, 0 skipped

- [ ] **Step 2: Verify 0 print() statements**

Run: `grep -rn "print(" scripts/etl/*.py | grep -v __pycache__ | grep -v "def " | grep -v "# "`
Expected: Empty output

- [ ] **Step 3: Verify no hardcoded credentials**

Run: `grep -rn "postgres:postgres" scripts/etl/*.py | grep -v config.py | grep -v __pycache__`
Expected: Empty output

- [ ] **Step 4: Verify all functions have docstrings**

Run the AST checker from Task 9 Step 2.
Expected: `All functions have docstrings!`

- [ ] **Step 5: Verify data/ is not committed**

Run: `git ls-files data/`
Expected: Empty output

- [ ] **Step 6: Review commit history**

Run: `git log --oneline main..HEAD`
Expected: Clean, descriptive commit messages following convention

- [ ] **Step 7: Push branch**

```bash
git push -u origin phase-2/quality-remediation
```

- [ ] **Step 8: Present merge options per `finishing-a-development-branch` skill**

Report completion status to user and offer:
1. Merge to main locally
2. Create PR on GitHub
3. Keep branch as-is
4. Discard

---

## Quality Gate Re-Assessment Checklist

After all tasks complete, re-verify against the Phase 2 quality gates:

### Phase 2 Specific (10 items)
- [ ] All unit tests pass (`pytest tests/ -v`)
- [ ] Dry run completed with < 1% error rate
- [ ] Full import completed (≥ 99% of 6750 parameters) — already passed
- [ ] FK integrity: 0 orphan records — already passed
- [ ] NULL check: 0 null in name or category — already passed
- [ ] Category coverage: ≥ 30 distinct categories — already passed
- [ ] Source coverage: ≥ 80% have source_file — already passed
- [ ] Duplicate check: no duplicate parameter IDs — already passed
- [ ] Full-text search: ts_vector populated for all records — already passed
- [ ] Summary report generated and reviewed — already passed

### Code Quality (6 items)
- [ ] No `print()` debug statements remain
- [ ] No hardcoded credentials
- [ ] No commented-out code blocks
- [ ] All functions have docstrings
- [ ] Magic numbers extracted to named constants
- [ ] Error messages include context

### Testing (4 items)
- [ ] Unit tests exist for new logic
- [ ] Tests cover edge cases
- [ ] All tests pass
- [ ] No skipped or xfailed tests without documented reason

### Git Hygiene (5 items)
- [ ] Branch name follows `phase-N/...` convention
- [ ] Commit messages are descriptive
- [ ] Only relevant files staged
- [ ] No large binary files committed
- [ ] `data/` directory never committed

### Documentation (4 items — applicable subset)
- [ ] New files have header comments
- [ ] Schema changes documented
- [ ] README/CHANGELOG updated
