"""化学式机械归一 —— 接口注入 normalize 阶段（ADR-0005，NFMA-2）。

FormulaNormalizer 是 transform 阶段可注入的接口：pymatgen 实现位于
extras 路径 :mod:`etl.formula_pymatgen`（``etl[chem]``），未安装
extras 时工厂降级为本模块的 stdlib 正则引擎，ETL 仍可完整运行。
正则引擎只认纯化学计量式（元素符号 + 整数/小数下标），无法归一
合金 wt.%、非计量式（UO2+x）等写法——这些留给 alias map 语义归一。
"""

import re
from dataclasses import dataclass
from typing import Protocol

from etl.logging_config import get_logger

logger = get_logger(__name__)

# 元素符号表（1-118，够核燃料域用）
ELEMENT_SYMBOLS = frozenset(
    [
        "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si",
        "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni",
        "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr", "Nb",
        "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe",
        "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho",
        "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
        "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np",
        "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg",
        "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
    ]
)

# 如 "UO2"、"U3Si2"、"UO2.0"、"ZrH1.5"；捕获 (符号, 下标) 段
_SEGMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*(?:\.\d+)?)")


@dataclass(frozen=True)
class FormulaResult:
    """一次化学式归一的结果。"""

    formula: str | None  # 归一后的化学式；无法解析为 None
    matched: bool
    engine: str  # "pymatgen" | "regex"


class FormulaNormalizer(Protocol):
    """化学式归一接口（ADR-0005）。"""

    def normalize(self, raw: str | None) -> FormulaResult:
        """尝试把 raw 材料串归一为化学式；失败返回 matched=False。"""
        ...


class RegexFormulaNormalizer:
    """stdlib 降级引擎：只认纯化学计量式。"""

    engine = "regex"

    def normalize(self, raw: str | None) -> FormulaResult:
        if not raw:
            return FormulaResult(None, False, self.engine)
        text = raw.strip()
        if not text or not re.fullmatch(r"[A-Z][A-Za-z0-9.]*", text):
            return FormulaResult(None, False, self.engine)
        pos = 0
        parts: list[str] = []
        for m in _SEGMENT_RE.finditer(text):
            if m.start() != pos:
                return FormulaResult(None, False, self.engine)
            symbol, count = m.group(1), m.group(2)
            if symbol not in ELEMENT_SYMBOLS:
                return FormulaResult(None, False, self.engine)
            parts.append(symbol + (count.rstrip(".") if count else ""))
            pos = m.end()
        if pos != len(text) or not parts:
            return FormulaResult(None, False, self.engine)
        return FormulaResult("".join(parts), True, self.engine)


def build_formula_normalizer() -> FormulaNormalizer:
    """工厂：优先 pymatgen 引擎（extras），缺失时明确降级到正则引擎。"""
    try:
        from etl.formula_pymatgen import PymatgenFormulaNormalizer
    except ImportError as e:  # pymatgen 未安装（extras 缺失）
        logger.warning(
            "pymatgen 不可用（%s）：FormulaNormalizer 降级为 stdlib 正则引擎，"
            "仅支持纯化学计量式归一。安装 etl[chem] 可启用完整引擎。",
            e,
        )
        return RegexFormulaNormalizer()
    return PymatgenFormulaNormalizer()
