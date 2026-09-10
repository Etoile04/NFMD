"""Tests for extract/transform wiring of confidence + formula injection."""

import json

from etl.acceptance import run_acceptance
from etl.extract import _to_extracted_record
from etl.formula import FormulaResult, RegexFormulaNormalizer
from etl.transform import _transform_one


def _make_normalizers(tmp_path, monkeypatch):
    from etl.normalize import MaterialNormalizer

    alias = tmp_path / "alias.json"
    alias.write_text(
        json.dumps(
            {
                "materials": [
                    {"canonical_name": "U-Mo alloy", "aliases": ["U-10Mo", "UMo"]},
                    {"canonical_name": "UO2", "aliases": ["UO2", "uranium dioxide"]},
                ],
                "non_material": [],
            }
        ),
        encoding="utf-8",
    )
    return MaterialNormalizer(str(alias)), RegexFormulaNormalizer()


class TestExtractConfidenceWiring:
    def test_dual_channel_metadata_derives_confidence(self):
        rec = _to_extracted_record(
            {
                "id": "x1",
                "name": "thermal conductivity",
                "value_type": "scalar",
                "value": 5.0,
                "channel_a": 5.0,
                "channel_b": 5.0,
                "self_audit": "yes",
            },
            "f.json",
        )
        assert rec.derived_confidence == "high"

    def test_no_metadata_derives_none(self):
        rec = _to_extracted_record({"id": "x2", "name": "n", "value": 1.0}, "f.json")
        assert rec.derived_confidence is None


class _NoFormula:
    engine = "test"

    def normalize(self, raw):
        return FormulaResult("UO2" if raw == "UO2" else None, raw == "UO2", "test")


class TestTransformInjection:
    def test_formula_normalizer_injected_into_transform(self, tmp_path, monkeypatch):
        mat_norm, _ = _make_normalizers(tmp_path, monkeypatch)
        rec = _to_extracted_record(
            {"id": "t1", "name": "k", "value_type": "scalar", "value": 1.0, "material": "UO2"},
            "f.json",
        )
        out = _transform_one(rec, mat_norm, _NoFormula())
        assert out.material_formula == "UO2"

    def test_derived_confidence_precedes_raw_label(self, tmp_path, monkeypatch):
        mat_norm, _ = _make_normalizers(tmp_path, monkeypatch)
        rec = _to_extracted_record(
            {
                "id": "t2",
                "name": "k",
                "value_type": "scalar",
                "value": 1.0,
                "confidence": "high",
                "channel_a": 1.0,
                "channel_b": 2.0,  # 双通道不一致 → low，覆盖自带 high
            },
            "f.json",
        )
        out = _transform_one(rec, mat_norm, _NoFormula())
        assert out.confidence == "low"

    def test_numeric_confidence_falls_back_to_label(self, tmp_path, monkeypatch):
        mat_norm, _ = _make_normalizers(tmp_path, monkeypatch)
        rec = _to_extracted_record(
            {"id": "t3", "name": "k", "value_type": "scalar", "value": 1.0, "confidence": 0.9},
            "f.json",
        )
        out = _transform_one(rec, mat_norm, _NoFormula())
        assert out.confidence == "high"


class TestAcceptanceGate:
    def _write_corpus(self, corpus):
        good = [
            {
                "id": f"g{i}",
                "name": f"param {i}",
                "value_type": "scalar",
                "value": float(i),
                "unit": "GPa",
                "category": "elastic",
                "confidence": 0.9,
            }
            for i in range(3)
        ]
        # 一条 error 级问题记录（缺值）
        (corpus / "a.json").write_text(json.dumps(good), encoding="utf-8")
        (corpus / "b.json").write_text(
            json.dumps([{"id": "bad", "name": "no value", "value_type": "scalar"}]),
            encoding="utf-8",
        )
        return corpus

    def test_run_acceptance_reports_success_rate_and_confidence(self, tmp_path, monkeypatch):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        self._write_corpus(corpus)
        alias = tmp_path / "alias.json"
        alias.write_text('{"materials": [], "non_material": []}', encoding="utf-8")
        report = run_acceptance(str(corpus), str(alias))
        assert report["records_extracted"] == 4
        assert report["records_valid"] == 3
        assert 0 < report["success_rate"] <= 1
        assert report["confidence_distribution"].get("high") == 3
        assert report["gate_passed"] is True
        assert report["formula_engine"] in ("regex", "pymatgen")
