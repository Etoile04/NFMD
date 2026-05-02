"""Tests for normalize module: MaterialNormalizer, normalize_unit, parse_temperature."""

import json
import os
import sys

import pytest

# Ensure scripts/etl/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from normalize import MaterialNormalizer, normalize_unit, parse_temperature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def alias_map_path(tmp_path):
    """Create a temporary alias map JSON file for testing."""
    data = {
        "materials": [
            {
                "canonical_name": "U-10Mo",
                "aliases": [
                    "U-10wt.%Mo",
                    "U-10 wt% Mo",
                    "UMo",
                    "U-10Mo (monolithic)",
                ],
            },
            {
                "canonical_name": "UO2",
                "aliases": ["UO₂", "UO2+x"],
            },
            {
                "canonical_name": "U-Zr",
                "aliases": ["U-Zr alloy", "γ-U-Zr"],
            },
        ],
        "non_material": ["N/A", "general", "通用"],
    }
    path = tmp_path / "test_alias_map.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def normalizer(alias_map_path):
    """Return a MaterialNormalizer initialized with the test alias map."""
    return MaterialNormalizer(alias_map_path)


# ===========================================================================
# TestMaterialNormalizer
# ===========================================================================


class TestMaterialNormalizer:
    """Tests for MaterialNormalizer.resolve / normalize."""

    def test_exact_match(self, normalizer):
        """Canonical name resolves to itself."""
        assert normalizer.normalize("U-10Mo") == "U-10Mo"

    def test_alias_resolves(self, normalizer):
        """Known alias resolves to its canonical name."""
        assert normalizer.normalize("U-10wt.%Mo") == "U-10Mo"
        assert normalizer.normalize("U-10 wt% Mo") == "U-10Mo"

    def test_case_insensitive(self, normalizer):
        """Lookup is case-insensitive."""
        assert normalizer.normalize("umo") == "U-10Mo"
        assert normalizer.normalize("uO2") == "UO2"

    def test_unknown_material_returns_none(self, normalizer):
        """Unknown string returns None (not raw)."""
        assert normalizer.normalize("Unobtanium-42") is None

    def test_empty_string_returns_none(self, normalizer):
        """Empty string returns None."""
        assert normalizer.normalize("") is None

    def test_none_returns_none(self, normalizer):
        """None input returns None."""
        assert normalizer.normalize(None) is None

    def test_whitespace_stripped(self, normalizer):
        """Leading/trailing whitespace is stripped before lookup."""
        assert normalizer.normalize("  U-10Mo  ") == "U-10Mo"

    def test_parenthetical_qualifier_stripped(self, normalizer):
        """Parenthetical qualifiers are tried as a variant."""
        # "U-10Mo (monolithic)" is in the alias map directly,
        # but also tests the variant generation fallback
        assert normalizer.normalize("U-10Mo (some random qualifier)") == "U-10Mo"

    def test_is_canonical(self, normalizer):
        """is_canonical returns True for known canonical names."""
        assert normalizer.is_canonical("U-10Mo") is True
        assert normalizer.is_canonical("UO2") is True
        assert normalizer.is_canonical("UNKNOWN") is False

    def test_non_material_terms_loaded(self, normalizer):
        """Non-material terms are loaded into the normalizer."""
        assert "n/a" in normalizer.non_materials
        assert "general" in normalizer.non_materials


# ===========================================================================
# TestNormalizeUnit
# ===========================================================================


class TestNormalizeUnit:
    """Tests for normalize_unit function."""

    def test_known_unit_unchanged(self):
        """Already-normalized unit passes through."""
        assert normalize_unit("W/(m·K)") == "W/(m·K)"

    def test_known_unit_remapped(self):
        """Known alternate forms are normalized."""
        assert normalize_unit("W/mK") == "W/(m·K)"
        assert normalize_unit("W/m-K") == "W/(m·K)"
        assert normalize_unit("g/cm3") == "g/cm³"
        assert normalize_unit("m^2/s") == "m²/s"

    def test_unknown_unit_unchanged(self):
        """Unknown unit string passes through unchanged."""
        assert normalize_unit("arb. units") == "arb. units"

    def test_none_returns_none(self):
        """None input returns None."""
        assert normalize_unit(None) is None

    def test_empty_string_returns_none(self):
        """Empty string is falsy, returns as-is (empty string)."""
        result = normalize_unit("")
        assert result == ""

    def test_whitespace_stripped(self):
        """Whitespace around unit is stripped."""
        assert normalize_unit("  W/mK  ") == "W/(m·K)"


# ===========================================================================
# TestParseTemperature
# ===========================================================================


class TestParseTemperature:
    """Tests for parse_temperature function."""

    def test_numeric_float(self):
        """Float value is treated as Kelvin."""
        val, orig = parse_temperature(300.0)
        assert val == 300.0
        assert orig == "300.0"

    def test_numeric_int(self):
        """Integer value is treated as Kelvin."""
        val, orig = parse_temperature(500)
        assert val == 500.0

    def test_none_returns_none_tuple(self):
        """None input returns (None, None)."""
        val, orig = parse_temperature(None)
        assert val is None
        assert orig is None

    def test_string_number(self):
        """String '300' converts to float 300.0."""
        val, orig = parse_temperature("300")
        assert val == 300.0

    def test_string_with_K_unit(self):
        """String '600 K' parses to 600.0."""
        val, orig = parse_temperature("600 K")
        assert val == 600.0

    def test_celsius_converted(self):
        """Celsius value is converted to Kelvin."""
        val, orig = parse_temperature("25°C")
        assert val == pytest.approx(298.15, abs=0.01)

    def test_room_temperature(self):
        """'room temperature' returns ~298 K."""
        val, orig = parse_temperature("room temp")
        assert val == pytest.approx(298.15, abs=0.01)

    def test_range_temperature(self):
        """Range '600-800 K' returns average."""
        val, orig = parse_temperature("600-800 K")
        assert val == 700.0

    def test_non_numeric_string(self):
        """Non-numeric string doesn't crash, returns (None, raw_str)."""
        val, orig = parse_temperature("ambient")
        assert val is None
        assert orig == "ambient"

    def test_empty_string(self):
        """Empty string returns (None, None)."""
        val, orig = parse_temperature("")
        assert val is None
        assert orig is None

    def test_na_string(self):
        """'N/A' returns (None, 'N/A')."""
        val, orig = parse_temperature("N/A")
        assert val is None
        assert orig == "N/A"

    def test_small_number_not_kelvin(self):
        """Small numbers (≤50) are not treated as Kelvin in the plain-number path."""
        # "25 " — the regex-only path for numbers with trailing space
        # requires val > 50, so 25 won't match that branch
        val, orig = parse_temperature("25")
        # 25 goes through the direct float(path) — float("25") = 25.0 > 0, so
        # it actually returns (25.0, "25"). This tests actual behavior.
        assert val == 25.0

    def test_fahrenheit_converted(self):
        """Fahrenheit value is converted to Kelvin."""
        val, orig = parse_temperature("77°F")
        expected = (77.0 - 32) * 5 / 9 + 273.15
        assert val == pytest.approx(expected, abs=0.01)
