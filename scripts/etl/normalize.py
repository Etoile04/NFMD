"""Material alias lookup, unit and temperature normalization."""

import json
import re
from typing import Any


class MaterialNormalizer:
    """Maps raw material strings to canonical material names."""

    def __init__(self, alias_map_path: str):
        """Load the alias map and build internal lookup structures.

        Args:
            alias_map_path: Path to the JSON alias-map file containing
                ``materials`` and ``non_material`` entries.
        """
        with open(alias_map_path, encoding="utf-8") as f:
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

    def normalize(self, raw_material: str | None) -> str | None:
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
#
# 受控词表 v2（NFMA-10，试点结论转化）：金标对照显示宽松/严格口径差
# 22 个百分点，主因是同一物理单位的序列化异构（Unicode 上标 vs ASCII
# `^` 形、`W/(cm*K)` vs `W/cm-C` 一类分隔符漂移）。归一分两层：
# ① :func:`_fold_ascii_exponents` / :func:`_unify_separators` 的机械折叠；
# ② 本表对机械折叠覆盖不到的形态做显式映射。表中 value 即规范形。
# 注意：激活新映射会改变后续 load 的 business key（unit 分量），存量
# parameters 行的回填属 🟡 需审批项——见 ADR-0006。
UNIT_NORMALIZE: dict[str, str] = {
    "m2/s": "m²/s",
    "m^2/s": "m²/s",
    "cm2/s": "cm²/s",
    "cm^2/s": "cm²/s",
    "W/mK": "W/(m·K)",
    "W/m-K": "W/(m·K)",
    "W/m K": "W/(m·K)",
    "W/m·K": "W/(m·K)",
    "W/(m·K)": "W/(m·K)",
    "W/(m K)": "W/(m·K)",
    "W/cmK": "W/(cm·K)",
    "W/cm-K": "W/(cm·K)",
    "W/cm K": "W/(cm·K)",
    "W/cm·K": "W/(cm·K)",
    "W/(cm·K)": "W/(cm·K)",
    "W/(cm K)": "W/(cm·K)",
    "W/cmC": "W/(cm·°C)",
    "W/cm-C": "W/(cm·°C)",
    "W/cm C": "W/(cm·°C)",
    "W/cm·C": "W/(cm·°C)",
    "W/(cm·°C)": "W/(cm·°C)",
    "W/(cm C)": "W/(cm·°C)",
    "W/cm²": "W/cm²",
    "W/cm2": "W/cm²",
    "J/m2": "J/m²",
    "J/m^2": "J/m²",
    "eV/atom": "eV/atom",
    "eV": "eV",
    "keV": "keV",
    "MeV": "MeV",
    "MeV/nucleon": "MeV/u",
    "MeV/u": "MeV/u",
    "MJ/m3": "MJ/m³",
    "kg/m3": "kg/m³",
    "g/cm3": "g/cm³",
    "fissions/cm3": "fissions/cm³",
    "GPa": "GPa",
    "MPa": "MPa",
    "dpa": "dpa",
    "10-6/K": "×10⁻⁶/K",
    "1/K": "K⁻¹",
    "K⁻¹": "K⁻¹",
    "°C": "°C",
    "at%": "at.%",
    "um": "μm",
    "x10⁻¹⁵": "×10⁻¹⁵",
    "x10²¹": "×10²¹",
}

# ASCII 指数 → Unicode 上标
_SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "-": "⁻", "+": "⁺",
}


def _fold_ascii_exponents(unit: str) -> str:
    """ASCII 指数形折叠为 Unicode 上标：m^2/s → m²/s、10^-15 → 10⁻¹⁵。

    仅折叠显式 `^` 形；连字符形（cm-2）与区间语义有歧义，不机械折叠，
    一律走显式别名表。
    """
    return re.sub(
        r"\^(-|\+)?(\d+)",
        lambda m: "".join(_SUPERSCRIPT_MAP[c] for c in (m.group(1) or "") + m.group(2)),
        unit,
    )


def _unify_separators(unit: str) -> str:
    """分隔符统一：`*` 视为乘号折叠为 `·`，空白折叠为单空格。"""
    return re.sub(r"\s+", " ", unit.replace("*", "·")).strip()


# 实际查找层：表键先经与 :func:`normalize_unit` 相同的机械折叠，保证
# "W/(cm*K)" 一类表项在统一分隔符后仍可命中；两层（精确/大小写不敏感）
# 均要求折叠后无键冲突。
_UNIT_LOOKUP: dict[str, str] = {}
_UNIT_LOOKUP_LOWER: dict[str, str] = {}
for _unit, _canonical in UNIT_NORMALIZE.items():
    _key = _unify_separators(_fold_ascii_exponents(_unit))
    assert _key not in _UNIT_LOOKUP, f"unit alias collision: {_unit!r}"
    _UNIT_LOOKUP[_key] = _canonical
    _lower_key = _key.lower()
    assert _lower_key not in _UNIT_LOOKUP_LOWER, f"unit alias collision: {_unit!r}"
    _UNIT_LOOKUP_LOWER[_lower_key] = _canonical


def normalize_unit(unit: str | None) -> str | None:
    """Normalize unit string to standard form.

    流程：机械折叠（指数上标化 + 分隔符统一）→ 精确别名 → 大小写
    不敏感别名；均未命中时原样返回（折叠后的）输入。
    """
    if not unit:
        return unit
    candidate = _unify_separators(_fold_ascii_exponents(unit.strip()))
    hit = _UNIT_LOOKUP.get(candidate)
    if hit is not None:
        return hit
    return _UNIT_LOOKUP_LOWER.get(candidate.lower(), candidate)


# Temperature parsing
def parse_temperature(raw: Any) -> tuple[float | None, str | None]:
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
