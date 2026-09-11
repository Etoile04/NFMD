"""全文抽取试点分析（NFMA-9）：双通道合并 + 金标对照评估。

对 ChatExtract 双通道（channel_a / channel_b，两轮互盲全文抽取）产物做
合并与金标对照：

- :func:`merge_channels` — 按同量匹配合并两通道记录，产出携带
  ``channel_a`` / ``channel_b`` / ``self_audit`` 元数据的 ETL 输入记录；
  自审计结果由外部按 ``pilot_id`` 回填。
- :func:`evaluate_against_gold` — 与金标（corpus-snapshot JSON）1:1 贪心
  匹配，按 value+unit（严格）与 value-only（宽松）两档量化 precision /
  recall / F1。

用法::

    uv run python -m etl.fulltext_pilot merge --slug <slug> ...
    uv run python -m etl.fulltext_pilot evaluate ...
"""

import argparse
import json
import math
import re
from pathlib import Path

from etl.confidence import derive_confidence
from etl.io_utils import write_json
from etl.logging_config import get_logger
from etl.path_safety import safe_open_read, safe_read_path

logger = get_logger(__name__)

_REL_TOL = 0.02  # 数值匹配的相对容差（金标多为转写值，2% 覆盖舍入差异）


def _canon_value(rec: dict):
    """记录取值的规范三元组：scalar / (min, max) / text。"""
    v = rec.get("value")
    if isinstance(v, list) and len(v) == 2:
        try:
            return ("range", float(v[0]), float(v[1]))
        except (TypeError, ValueError):
            return ("text", str(v), None)
    if isinstance(v, bool) or v is None:
        return ("text", None, None)
    if isinstance(v, (int, float)):
        return ("scalar", float(v), None)
    try:
        return ("scalar", float(str(v)), None)
    except ValueError:
        return ("text", str(v), None)


def _close(a: float, b: float, tol: float = _REL_TOL) -> bool:
    if a == b:
        return True
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-12)


def values_match(ra: dict, rb: dict, tol: float = _REL_TOL) -> bool:
    """两记录取值是否一致（scalar 相近，或 range 两端均相近）。"""
    ta, va, va2 = _canon_value(ra)
    tb, vb, vb2 = _canon_value(rb)
    if ta != tb:
        return False
    if ta == "scalar":
        return _close(va, vb, tol)
    if ta == "range":
        return _close(va, vb, tol) and _close(va2, vb2, tol)
    return str(va).strip() == str(rb).strip()


def _name_tokens(rec: dict) -> set[str]:
    stop = {"of", "the", "in", "at", "for", "a", "an", "and", "to", "with", "u"}
    return {t for t in re.split(r"[^a-z0-9]+", (rec.get("name_en") or "").lower()) if t and t not in stop}


def merge_channels(records_a: list[dict], records_b: list[dict], slug: str) -> list[dict]:
    """合并双通道：同 category 且取值一致（或名称 token 高重叠）视为同量。

    匹配优先级：值一致 > 名称 token Jaccard ≥ 0.5。未匹配记录保留为单
    通道。返回记录携带 ``channel_a`` / ``channel_b`` / ``self_audit=None``
    与 ``pilot_id``（自审计结果按 id 回填）。
    """
    merged: list[dict] = []
    used_b: set[int] = set()

    for ra in records_a:
        match = None
        # 值一致优先
        for j, rb in enumerate(records_b):
            if j in used_b or rb.get("category") != ra.get("category"):
                continue
            if values_match(ra, rb):
                match = j
                break
        # 名称相似兜底（同 category 且 token 重叠）
        if match is None:
            ta = _name_tokens(ra)
            best_j, best_jac = None, 0.0
            for j, rb in enumerate(records_b):
                if j in used_b or rb.get("category") != ra.get("category"):
                    continue
                tb = _name_tokens(rb)
                jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
                if jac > best_jac:
                    best_jac, best_j = jac, j
            if best_jac >= 0.5:
                match = best_j
        if match is not None:
            used_b.add(match)
            base, other = ra, records_b[match]
            merged.append(
                _make_record(base, slug, channel_a={"value": base.get("value")},
                             channel_b={"value": other.get("value")},
                             evidence_b=other.get("source_sentence"))
            )
        else:
            merged.append(_make_record(ra, slug, channel_a={"value": ra.get("value")}))

    for j, rb in enumerate(records_b):
        if j not in used_b:
            merged.append(_make_record(rb, slug, channel_b={"value": rb.get("value")}))
    return merged


def _make_record(base: dict, slug: str, *, channel_a=None, channel_b=None, evidence_b=None) -> dict:
    rec = dict(base)
    rec["pilot_id"] = f"{slug}_pilot_{len(rec.get('_seq', '')) or ''}"  # 由调用方重排
    rec["source_file"] = slug
    rec["channel_a"] = channel_a
    rec["channel_b"] = channel_b
    if evidence_b:
        rec["evidence_channel_b"] = evidence_b
    rec["self_audit"] = None
    return rec


def apply_self_audit(records: list[dict], audit: dict[str, str]) -> int:
    """按 ``pilot_id`` 回填自审计 yes/no；返回命中数。"""
    hit = 0
    for rec in records:
        ans = audit.get(rec["pilot_id"])
        if ans is not None:
            rec["self_audit"] = ans
            hit += 1
        rec["derived_confidence"] = derive_confidence(
            rec.get("channel_a"), rec.get("channel_b"), rec.get("self_audit")
        )
    return hit


def renumber_pilot_ids(records: list[dict], slug: str) -> None:
    for idx, rec in enumerate(records):
        rec["pilot_id"] = f"{slug}_pilot_{idx:03d}"


def _gold_values(gold_rec: dict):
    if gold_rec.get("value_type") == "range":
        return ("range", gold_rec.get("value_min"), gold_rec.get("value_max"))
    if gold_rec.get("value_scalar") is not None:
        return ("scalar", float(gold_rec["value_scalar"]), None)
    if gold_rec.get("value_str") not in (None, ""):
        try:
            return ("scalar", float(gold_rec["value_str"]), None)
        except ValueError:
            return ("text", str(gold_rec["value_str"]), None)
    return ("text", None, None)


def _extracted_value(rec: dict):
    v = rec.get("value")
    if rec.get("value_type") == "range" and isinstance(v, list) and len(v) == 2:
        try:
            return ("range", float(v[0]), float(v[1]))
        except (TypeError, ValueError):
            return ("text", str(v), None)
    return _canon_value(rec)


def evaluate_against_gold(records: list[dict], gold: list[dict], tol: float = _REL_TOL) -> dict:
    """抽取记录 vs 金标 1:1 贪心匹配，输出 precision / recall / F1。

    两档口径：strict 要求 value 匹配且 unit 归一后一致；lenient 只要求
    value 匹配（同值多记录时 1:1 消耗，不重复计数）。
    """
    def unit_key(u):
        return re.sub(r"[\s·^\-_/（）()]", "", (u or "").lower())

    def match_extracted(gold_rec, extracted, used, require_unit):
        tg, vg1, vg2 = _gold_values(gold_rec)
        for idx, rec in enumerate(extracted):
            if idx in used:
                continue
            te, ve1, ve2 = _extracted_value(rec)
            if tg != te:
                # 金标 scalar vs 抽取 range 不互匹配（量纲口径不同）
                continue
            ok = False
            if tg == "scalar":
                ok = _close(vg1, ve1, tol)
            elif tg == "range":
                ok = _close(vg1, ve1, tol) and _close(vg2, ve2, tol)
            else:
                ok = str(vg1).strip() == str(ve1).strip()
            if ok and require_unit and unit_key(gold_rec.get("unit")) != unit_key(rec.get("unit")):
                continue
            if ok:
                return idx
        return None

    out = {}
    for mode, require_unit in (("strict", True), ("lenient", False)):
        used: set[int] = set()
        tp = 0
        matched_gold_ids = []
        for g in gold:
            idx = match_extracted(g, records, used, require_unit)
            if idx is not None:
                used.add(idx)
                tp += 1
                matched_gold_ids.append(g.get("id"))
        fp = len(records) - tp
        fn = len(gold) - tp
        precision = tp / len(records) if records else None
        recall = tp / len(gold) if gold else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall
            else None
        )
        out[mode] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "matched_gold_ids": matched_gold_ids,
        }
    return out


def _load_json(path: str):
    with safe_open_read(safe_read_path(path), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="NFMA-9 全文抽取试点：合并 + 评估")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_merge = sub.add_argument("merge", help="合并双通道产物")
    p_merge.add_argument("--slug", required=True)
    p_merge.add_argument("--channel-a", required=True)
    p_merge.add_argument("--channel-b", required=True)
    p_merge.add_argument("--output", required=True)

    p_eval = sub.add_argument("evaluate", help="对照金标评估")
    p_eval.add_argument("--records-dir", required=True)
    p_eval.add_argument("--gold-dir", required=True)
    p_eval.add_argument("--slugs", nargs="+", required=True)
    p_eval.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.cmd == "merge":
        recs = merge_channels(_load_json(args.channel_a), _load_json(args.channel_b), args.slug)
        renumber_pilot_ids(recs, args.slug)
        write_json(args.output, recs)
        print(f"merged {len(recs)} records -> {args.output}")
    else:
        results = {}
        for slug in args.slugs:
            recs = _load_json(str(Path(args.records_dir) / f"{slug}.json"))
            gold = _load_json(str(Path(args.gold_dir) / f"{slug}.json"))
            if isinstance(gold, dict):
                gold = gold.get("parameters", [gold])
            results[slug] = evaluate_against_gold(recs, gold)
            results[slug]["extracted"] = len(recs)
            results[slug]["gold"] = len(gold)
        write_json(args.output, results)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
