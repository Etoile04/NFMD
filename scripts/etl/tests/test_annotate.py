"""Interface tests for the human-annotation tooling (guideline: docs/annotation/guideline.md).

Seams under test (pre-agreed, no internals):
1. form → record build → validate_records verdict;
2. selection text → source_sentence extraction (pure);
3. dual-annotator records → pairing / arbitration merge (pure, reuses
   fulltext_pilot.values_match);
4. export paths land inside path_safety allowlist.
"""

import json

import pytest
from fastapi.testclient import TestClient

from etl import annotate
from etl.annotate import (
    arbitrate,
    bucketed_report,
    build_record,
    check_record,
    export_gold,
    inter_annotator_stats,
    pair_annotations,
    trim_source_sentence,
)
from etl.fulltext_pilot import evaluate_against_gold

VALID_FORM = {
    "name_en": "displacement threshold energy of U in SRIM calculation",
    "value_type": "scalar",
    "value_scalar": 35.6,
    "unit": "eV",
    "unit_canonical": "eV",
    "material": "U",
    "category": "simulation_parameter",
    "source_sentence": "the displacement threshold energy of U was 35.6 eV",
    "source_location": "Table 2",
    "notes": "SRIM input",
}


class TestBuildAndValidate:
    """Seam 1: record construction + validate_records verdict."""

    def test_valid_form_passes_rules(self):
        rec = build_record(VALID_FORM, slug="paper_x", annotator="ann1", seq=1)
        issues = check_record(rec)
        assert [i for i in issues if i["severity"] == "error"] == []
        assert rec["record_id"] == "paper_x_ann1_001"
        assert rec["source_file"] == "paper_x"

    def test_unit_canonical_autofilled_from_normalize_unit(self):
        form = dict(VALID_FORM, unit="eV", unit_canonical=None)
        rec = build_record(form, slug="paper_x", annotator="ann1", seq=1)
        assert rec["unit_canonical"] == "eV"

    def test_uncertainty_stays_its_own_field(self):
        form = dict(VALID_FORM, uncertainty="0.3")
        rec = build_record(form, slug="paper_x", annotator="ann1", seq=1)
        assert rec["uncertainty"] == "0.3"
        assert rec["value_min"] is None and rec["value_max"] is None

    def test_generic_name_is_rejected(self):
        form = dict(VALID_FORM, name_en="parameter")
        rec = build_record(form, slug="paper_x", annotator="ann1", seq=1)
        issues = check_record(rec)
        assert any(i["code"] == "GENERIC_NAME" for i in issues)

    def test_range_form_min_max(self):
        form = dict(VALID_FORM, value_type="range", value_scalar=None,
                    value_min=0.7, value_max=5.2)
        rec = build_record(form, slug="paper_x", annotator="ann1", seq=1)
        assert rec["value"] == [0.7, 5.2]
        assert not [i for i in check_record(rec) if i["severity"] == "error"]


class TestSourceSentence:
    """Seam 2: selection → source_sentence (pure)."""

    def test_trims_to_two_sentences(self):
        text = "First sentence about swelling. Second one. Third one."
        assert trim_source_sentence(text) == "First sentence about swelling. Second one."

    def test_keeps_short_selection_verbatim(self):
        text = "value = 35.6 eV (Table 2)"
        assert trim_source_sentence(text) == text

    def test_collapses_whitespace(self):
        assert trim_source_sentence("a   b\n\nc") == "a b c"


class TestPairingAndArbitration:
    """Seam 3: dual annotator → match / arbitrate → gold."""

    def _recs(self, annotator: str) -> list[dict]:
        base = [build_record(dict(VALID_FORM, value_scalar=v), slug="paper_x",
                             annotator=annotator, seq=i + 1)
                for i, v in enumerate((35.6, 60.0))]
        extra = build_record(dict(VALID_FORM, value_scalar=99.0,
                                  name_en="swelling strain of U"),
                             slug="paper_x", annotator=annotator, seq=3)
        return base + [extra]

    def test_pairs_matching_records(self):
        pairs = pair_annotations(self._recs("ann1"), self._recs("ann2"))
        matched = [p for p in pairs if p["a"] is not None and p["b"] is not None]
        assert len(matched) == 3  # 35.6, 60.0, and 99.0 all match by name+value

    def test_single_sided_pair(self):
        a = self._recs("ann1")
        b = self._recs("ann2")[:-1]
        pairs = pair_annotations(a, b)
        singles = [p for p in pairs if p["a"] is None or p["b"] is None]
        assert len(singles) == 1

    def test_stats_match_rate(self):
        stats = inter_annotator_stats(pair_annotations(self._recs("ann1"), self._recs("ann2")))
        assert stats["matched"] == 3
        assert stats["match_rate"] == 1.0

    def test_arbitrate_picks_side(self):
        pairs = pair_annotations(self._recs("ann1"), self._recs("ann2"))
        decisions = [
            {"pair_id": p["pair_id"], "choice": "a" if p["b"] is None else "b"}
            for p in pairs
        ]
        gold = arbitrate(pairs, decisions, slug="paper_x")
        assert len(gold) == 3
        assert all(g["source_file"] == "paper_x" for g in gold)

    def test_gold_is_consumable_by_evaluate_against_gold(self):
        pairs = pair_annotations(self._recs("ann1"), self._recs("ann2"))
        decisions = [{"pair_id": p["pair_id"], "choice": "a"} for p in pairs]
        gold = arbitrate(pairs, decisions, slug="paper_x")
        extracted = [dict(r) for r in gold]  # perfect extraction
        result = evaluate_against_gold(extracted, gold)
        assert result["strict"]["precision"] == 1.0
        assert result["strict"]["recall"] == 1.0


class TestBucketedReport:
    """D3: gold vs extraction 分桶（漏抽/值错/单位错/条件归属错）。"""

    def _gold(self):
        return [
            build_record(VALID_FORM, slug="paper_x", annotator="g", seq=1),  # matched
            build_record(dict(VALID_FORM, value_scalar=60.0,
                              name_en="displacement threshold energy of Mo"),
                         slug="paper_x", annotator="g", seq=2),
            build_record(dict(VALID_FORM, name_en="swelling strain of U"),
                         slug="paper_x", annotator="g", seq=3),  # missed
        ]

    def test_matched_value_unit_condition_buckets(self):
        gold = self._gold()
        extracted = [
            gold[0],  # perfect
            dict(gold[1], value_scalar=70.0, value=70.0),  # 值错（超 2% 容差）
        ]
        rep = bucketed_report(extracted, gold)
        assert rep["counts"] == {"matched": 1, "missed": 1, "value_wrong": 1,
                                 "unit_wrong": 0, "condition_wrong": 0}
        assert rep["pilot_metrics"]["lenient"]["recall"] is not None

    def test_unit_bucket(self):
        gold = self._gold()[:1]
        extracted = [dict(gold[0], unit="J")]
        rep = bucketed_report(extracted, gold)
        assert rep["counts"]["unit_wrong"] == 1

    def test_condition_bucket(self):
        gold = self._gold()[:1]
        extracted = [dict(gold[0], material="U-Mo")]
        rep = bucketed_report(extracted, gold)
        assert rep["counts"]["condition_wrong"] == 1


class TestExport:
    """Seam 4: export lands inside path_safety allowlist."""

    def test_save_and_export_gold(self, tmp_path, monkeypatch):
        out = tmp_path / "anno"
        recs = [build_record(VALID_FORM, slug="paper_x", annotator="ann1", seq=1)]
        annotate.save_annotation("paper_x", "ann1", recs, str(out))
        assert json.loads((out / "ann1" / "paper_x.json").read_text()) == recs

        gold = arbitrate(
            pair_annotations(recs, [build_record(VALID_FORM, slug="paper_x", annotator="ann2", seq=1)]),
            None, slug="paper_x",
        )
        path = export_gold("paper_x", gold, str(out))
        assert path.endswith(str(out / "gold" / "paper_x.json"))
        assert json.loads((out / "gold" / "paper_x.json").read_text()) == gold

    def test_export_rejects_escape(self, tmp_path):
        with pytest.raises(ValueError):
            export_gold("../evil", [dict(VALID_FORM)], str(tmp_path))


class TestWebApp:
    """HTTP layer via TestClient, source dir = tmp fixtures."""

    @pytest.fixture
    def client(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "paper_x.txt").write_text("The value was 35.6 eV. See Table 2.")
        out = tmp_path / "out"
        app = annotate.create_app(source_dir=str(src), out_dir=str(out))
        return TestClient(app)

    def test_fulltext_roundtrip(self, client):
        r = client.get("/api/fulltext/paper_x")
        assert r.status_code == 200
        assert "35.6 eV" in r.json()["text"]

    def test_fulltext_rejects_unknown_slug(self, client):
        assert client.get("/api/fulltext/nope").status_code == 404

    def test_post_records_validates_and_saves(self, client):
        r = client.post("/api/records/ann1/paper_x", json={"records": [VALID_FORM]})
        assert r.status_code == 200, r.text
        listing = client.get("/api/records/ann1/paper_x")
        assert len(listing.json()["records"]) == 1

    def test_post_records_blocks_invalid(self, client):
        bad = dict(VALID_FORM, name_en="parameter")
        r = client.post("/api/records/ann1/paper_x", json={"records": [bad]})
        assert r.status_code == 422
        assert any(i["code"] == "GENERIC_NAME" for i in r.json()["detail"]["issues"])

    def test_unit_canonical_endpoint(self, client):
        r = client.get("/api/unit-canonical", params={"unit": "eV"})
        assert r.status_code == 200
        assert r.json()["canonical"] == "eV"

    def test_arbitrate_flow(self, client):
        for ann in ("ann1", "ann2"):
            client.post(f"/api/records/{ann}/paper_x", json={"records": [VALID_FORM]})
        pairs = client.get("/api/arbitrate/paper_x", params={"a": "ann1", "b": "ann2"})
        assert pairs.status_code == 200
        assert pairs.json()["stats"]["matched"] == 1
        decisions = [{"pair_id": p["pair_id"], "choice": "a"} for p in pairs.json()["pairs"]]
        done = client.post("/api/arbitrate/paper_x",
                           json={"a": "ann1", "b": "ann2", "decisions": decisions})
        assert done.status_code == 200
        assert done.json()["gold_count"] == 1
