"""Tests for FormulaNormalizer interface + pymatgen extras degradation."""

import contextlib
import importlib
import sys
from unittest import mock

import pytest

from etl.formula import FormulaResult, RegexFormulaNormalizer, build_formula_normalizer


class TestRegexFormulaNormalizer:
    def setup_method(self):
        self.norm = RegexFormulaNormalizer()

    def test_plain_stoichiometric(self):
        result = self.norm.normalize("UO2")
        assert result.matched and result.formula == "UO2"
        assert self.norm.normalize("U3Si2").formula == "U3Si2"
        assert self.norm.normalize("ZrH1.5").formula == "ZrH1.5"

    def test_whitespace_stripped(self):
        result = self.norm.normalize("  UO2 ")
        assert result.matched and result.formula == "UO2"

    def test_alloy_notation_not_matched(self):
        # 降级行为：合金/自由文本留给 alias map 语义归一
        assert not self.norm.normalize("U-10Mo").matched
        assert not self.norm.normalize("U-10 wt.%Mo").matched
        assert not self.norm.normalize("UO2+x").matched

    def test_unknown_symbol_rejected(self):
        assert not self.norm.normalize("Xx2Yz").matched

    def test_empty_and_none(self):
        assert not self.norm.normalize(None).matched
        assert not self.norm.normalize("").matched

    def test_result_carries_engine(self):
        assert self.norm.normalize("UO2").engine == "regex"


class TestFactoryDegradation:
    def test_missing_pymatgen_degrades_to_regex(self):
        # extras 缺失：formula_pymatgen 顶层 import pymatgen 失败
        with mock.patch.dict(sys.modules, {"pymatgen.core.composition": None}):
            # 清缓存强制重导入 extras 路径
            sys.modules.pop("etl.formula_pymatgen", None)
            norm = build_formula_normalizer()
            assert isinstance(norm, RegexFormulaNormalizer)

    def test_with_pymatgen_installed_uses_pymatgen(self):
        pytest.importorskip("pymatgen")
        sys.modules.pop("etl.formula_pymatgen", None)
        norm = build_formula_normalizer()
        assert norm.engine == "pymatgen"
        result = norm.normalize("UO2")
        assert result.matched and result.formula == "UO2"

    def teardown_method(self):
        sys.modules.pop("etl.formula_pymatgen", None)
        # pymatgen extras 未安装属合法状态，重导入失败不视为 teardown 错误
        with contextlib.suppress(ImportError):
            importlib.import_module("etl.formula_pymatgen")


class TestFormulaResultShape:
    def test_frozen_dataclass(self):
        import dataclasses

        r = FormulaResult("UO2", True, "regex")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.matched = False
