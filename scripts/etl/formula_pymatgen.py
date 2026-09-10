"""pymatgen 化学式归一引擎 —— extras 路径（``etl[chem]``，ADR-0005）。

本模块顶层 import pymatgen，只有安装了 extras 才可导入；
:func:`etl.formula.build_formula_normalizer` 以 try/except ImportError
守卫调用。合金 wt.%、非计量式（UO2+x）等 pymatgen 也无法解析的写法
返回 matched=False，由调用方回退 alias map 语义归一。
"""

from pymatgen.core.composition import Composition

from etl.formula import FormulaResult


class PymatgenFormulaNormalizer:
    """pymatgen Composition 驱动的化学式归一/校验。"""

    engine = "pymatgen"

    def normalize(self, raw: str | None) -> FormulaResult:
        if not raw:
            return FormulaResult(None, False, self.engine)
        text = raw.strip()
        if not text:
            return FormulaResult(None, False, self.engine)
        try:
            comp = Composition(text)
            formula = comp.reduced_formula
        except (ValueError, KeyError, IndexError, TypeError):
            # pymatgen 解析失败（合金 wt.%、"U-10Mo"、自由文本等）
            return FormulaResult(None, False, self.engine)
        if not formula or formula == "None":
            return FormulaResult(None, False, self.engine)
        return FormulaResult(formula, True, self.engine)
