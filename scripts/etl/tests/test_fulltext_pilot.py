"""NFMA-9 全文抽取试点模块测试：双通道合并 + 金标评估口径。"""

from etl.fulltext_pilot import (
    apply_self_audit,
    evaluate_against_gold,
    merge_channels,
    renumber_pilot_ids,
)


def _rec(name, value, unit="eV", category="diffusion", **kw):
    base = {
        "name_en": name,
        "value_type": "scalar",
        "value": value,
        "unit": unit,
        "category": category,
        "source_sentence": "The value is stated here.",
    }
    base.update(kw)
    return base


class TestMergeChannels:
    def test_value_agreement_pairs_channels(self):
        a = [_rec("Xe migration energy in U-Mo", 2.0)]
        b = [_rec("migration energy of Xe", 2.0)]
        out = merge_channels(a, b, "s")
        assert len(out) == 1
        assert out[0]["channel_a"] == {"value": 2.0}
        assert out[0]["channel_b"] == {"value": 2.0}

    def test_value_disagreement_pairs_with_low_confidence(self):
        from etl.confidence import derive_confidence

        a = [_rec("migration energy", 2.0)]
        b = [_rec("migration energy", 2.5)]
        out = merge_channels(a, b, "s")
        assert len(out) == 1
        assert out[0]["channel_a"] == {"value": 2.0}
        assert out[0]["channel_b"] == {"value": 2.5}
        assert derive_confidence(out[0]["channel_a"], out[0]["channel_b"], None) == "low"

    def test_name_similarity_fallback(self):
        a = [_rec("vacancy formation energy in gamma U-Mo", 1.5)]
        b = [_rec("formation energy of vacancy gamma U-Mo", 1.7)]
        out = merge_channels(a, b, "s")
        assert len(out) == 1
        assert out[0]["channel_a"] is not None and out[0]["channel_b"] is not None

    def test_range_value_agreement_pairs_channels(self):
        a = [_rec("swelling range", [4.8, 6.4])]
        a[0]["value_type"] = "range"
        b = [_rec("swelling range reported", [4.8, 6.5])]
        b[0]["value_type"] = "range"
        out = merge_channels(a, b, "s")
        assert len(out) == 1
        assert out[0]["channel_a"] == {"value": [4.8, 6.4]}
        assert out[0]["channel_b"] == {"value": [4.8, 6.5]}

    def test_b_only_record_kept(self):
        a = [_rec("migration energy", 2.0)]
        b = [_rec("migration energy", 2.0), _rec("bubble radius", 5.0, "nm", "bubble")]
        out = merge_channels(a, b, "s")
        assert len(out) == 2
        b_only = next(r for r in out if "bubble" in r["name_en"])
        assert b_only["channel_a"] is None
        assert b_only["channel_b"] == {"value": 5.0}

    def test_pilot_ids_and_renumber(self):
        out = merge_channels([_rec("x", 1), _rec("y", 2)], [], "slug")
        renumber_pilot_ids(out, "slug")
        assert [r["pilot_id"] for r in out] == ["slug_pilot_000", "slug_pilot_001"]
        assert out[0]["source_file"] == "slug"


class TestApplySelfAudit:
    def test_confidence_derivation_wired(self):
        recs = merge_channels([_rec("e", 1.0)], [_rec("e", 1.0)], "s")
        renumber_pilot_ids(recs, "s")
        hit = apply_self_audit(recs, {recs[0]["pilot_id"]: "yes"})
        assert hit == 1
        assert recs[0]["derived_confidence"] == "high"

    def test_audit_doubt_downgrades(self):
        recs = merge_channels([_rec("e", 1.0)], [_rec("e", 1.0)], "s")
        renumber_pilot_ids(recs, "s")
        apply_self_audit(recs, {recs[0]["pilot_id"]: "no"})
        assert recs[0]["derived_confidence"] == "medium"


class TestEvaluateAgainstGold:
    def test_perfect_match(self):
        recs = [_rec("fission rate", 5e13, "cm-3s-1", "irradiation")]
        gold = [{
            "id": "g0", "value_type": "scalar", "value_scalar": 5e13,
            "unit": "cm⁻³s⁻¹",
        }]
        r = evaluate_against_gold(recs, gold)
        assert r["lenient"]["precision"] == 1.0 and r["lenient"]["recall"] == 1.0

    def test_unit_mismatch_strict_only(self):
        recs = [_rec("fission rate", 5e13, "cm-3s-1", "irradiation")]
        gold = [{
            "id": "g0", "value_type": "scalar", "value_scalar": 5e13,
            "unit": "K",
        }]
        r = evaluate_against_gold(recs, gold)
        assert r["lenient"]["true_positive"] == 1
        assert r["strict"]["true_positive"] == 0

    def test_range_requires_both_ends(self):
        recs = [_rec("swelling", [4.8e13, 6.4e13], "cm-3s-1", "irradiation")]
        recs[0]["value_type"] = "range"
        gold = [{
            "id": "g0", "value_type": "range",
            "value_min": 4.8e13, "value_max": 6.4e13, "unit": "cm-3s-1",
        }]
        r = evaluate_against_gold(recs, gold)
        assert r["strict"]["true_positive"] == 1
        gold_partial = [{
            "id": "g1", "value_type": "range",
            "value_min": 4.8e13, "value_max": 7.0e13, "unit": "cm-3s-1",
        }]
        assert evaluate_against_gold(recs, gold_partial)["lenient"]["true_positive"] == 0

    def test_one_to_one_no_double_count(self):
        recs = [_rec("temp A", 300.0, "K", "thermal")]
        gold = [
            {"id": "g0", "value_type": "scalar", "value_scalar": 300.0, "unit": "K"},
            {"id": "g1", "value_type": "scalar", "value_scalar": 300.0, "unit": "K"},
        ]
        r = evaluate_against_gold(recs, gold)
        assert r["lenient"]["true_positive"] == 1
        assert r["lenient"]["recall"] == 0.5
        assert r["lenient"]["false_negative"] == 1

    def test_metrics_arithmetic(self):
        recs = [_rec("a", 1.0), _rec("b", 2.0), _rec("c", 3.0)]
        gold = [
            {"id": "g0", "value_type": "scalar", "value_scalar": 1.0, "unit": "eV"},
            {"id": "g1", "value_type": "scalar", "value_scalar": 9.0, "unit": "eV"},
        ]
        r = evaluate_against_gold(recs, gold)
        assert r["lenient"]["precision"] == round(1 / 3, 4)
        assert r["lenient"]["recall"] == 0.5
        assert r["lenient"]["f1"] == round(2 * (1 / 3) * 0.5 / (1 / 3 + 0.5), 4)
