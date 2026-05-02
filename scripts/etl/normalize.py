"""Material alias lookup, unit and temperature normalization."""

import json
import re
from typing import Optional


class MaterialNormalizer:
    """Maps raw material strings to canonical material names."""

    def __init__(self, alias_map_path: str):
        """Load the alias map and build internal lookup structures.

        Args:
            alias_map_path: Path to the JSON alias-map file containing
                ``materials`` and ``non_material`` entries.
        """
        with open(alias_map_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Build alias -> canonical_name lookup
        self.alias_to_canonical: dict[str, str] = {}
        self.canonical_set: set[str] = set()

        for mat in data.get("materials", []):
            canon = mat["canonical_name"]
            self.canonical_set.add(canon)
            # Self-mapping
            self.alias_to_canonical[canon.lower()] = canon
            # All aliases
            for alias in mat.get("aliases", []):
                self.alias_to_canonical[alias.lower()] = canon

        # Non-material terms (to detect non-material entries)
        self.non_materials: set[str] = set()
        for nm in data.get("non_material", []):
            if isinstance(nm, str):
                self.non_materials.add(nm.lower())
            elif isinstance(nm, dict):
                self.non_materials.add(nm.get("name", "").lower())

    def normalize(self, raw_material: Optional[str]) -> Optional[str]:
        """Return canonical name or None if unmapped."""
        if not raw_material:
            return None
        raw = raw_material.strip()
        # Direct match (case-insensitive)
        result = self.alias_to_canonical.get(raw.lower())
        if result:
            return result
        # Try stripping common suffixes/prefixes
        for variant in self._generate_variants(raw):
            result = self.alias_to_canonical.get(variant.lower())
            if result:
                return result
        return None

    def _generate_variants(self, raw: str) -> list[str]:
        """Generate variant spellings to try."""
        variants = []
        # Remove parenthetical qualifiers
        cleaned = re.sub(r'\s*\([^)]*\)', '', raw).strip()
        if cleaned != raw:
            variants.append(cleaned)
        # Remove extra spaces
        variants.append(re.sub(r'\s+', ' ', raw).strip())
        # Remove trailing periods
        if raw.endswith('.'):
            variants.append(raw.rstrip('.').strip())
        return variants

    def is_canonical(self, name: str) -> bool:
        """Check whether *name* is a known canonical material name.

        Args:
            name: Material name to check.

        Returns:
            True if *name* is in the canonical set, False otherwise.
        """
        return name in self.canonical_set


# Unit normalization dictionary
UNIT_NORMALIZE: dict[str, str] = {
    "m2/s": "m²/s",
    "m^2/s": "m²/s",
    "cm2/s": "cm²/s",
    "cm^2/s": "cm²/s",
    "W/mK": "W/(m·K)",
    "W/m-K": "W/(m·K)",
    "W/m K": "W/(m·K)",
    "J/m2": "J/m²",
    "J/m^2": "J/m²",
    "eV/atom": "eV/atom",
    "MJ/m3": "MJ/m³",
    "kg/m3": "kg/m³",
    "g/cm3": "g/cm³",
    "10-6/K": "×10⁻⁶/K",
    "1/K": "K⁻¹",
}


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Normalize unit string to standard form."""
    if not unit:
        return unit
    return UNIT_NORMALIZE.get(unit.strip(), unit.strip())


# Temperature parsing
def parse_temperature(raw: Any) -> tuple[Optional[float], Optional[str]]:
    """Parse temperature value. Returns (kelvin, original_string)."""
    if raw is None:
        return None, None

    raw_str = str(raw).strip()
    if not raw_str or raw_str.lower() in ("none", "null", "n/a", "-"):
        return None, raw_str if raw_str else None

    # Try direct numeric (assume Kelvin)
    try:
        val = float(raw_str)
        if val > 0:
            return val, raw_str
    except (ValueError, TypeError):
        pass

    # Pattern: number followed by unit
    # Kelvin
    m = re.match(r'^([0-9.]+)\s*K$', raw_str, re.IGNORECASE)
    if m:
        return float(m.group(1)), raw_str

    # Celsius
    m = re.match(r'^([0-9.]+)\s*[°]?\s*C(?:elsius)?$', raw_str, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 273.15, raw_str

    # Fahrenheit
    m = re.match(r'^([0-9.]+)\s*[°]?\s*F(?:ahrenheit)?$', raw_str, re.IGNORECASE)
    if m:
        return (float(m.group(1)) - 32) * 5 / 9 + 273.15, raw_str

    # Range like "600-800 K"
    m = re.match(r'^([0-9.]+)\s*[-–]\s*([0-9.]+)\s*K$', raw_str, re.IGNORECASE)
    if m:
        avg = (float(m.group(1)) + float(m.group(2))) / 2
        return avg, raw_str

    # "room temperature" etc.
    if "room" in raw_str.lower():
        return 298.15, raw_str

    # Just a number with space (assume K)
    m = re.match(r'^([0-9.]+)\s*$', raw_str)
    if m:
        val = float(m.group(1))
        if val > 50:  # likely Kelvin
            return val, raw_str

    return None, raw_str
