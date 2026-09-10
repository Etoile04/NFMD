"""compare_runs（NFMA-8）单测：指标统计与 Markdown 渲染。"""

import json

from etl.compare_runs import collect_metrics, render_markdown


def _write_run(root, *, transformed=True, conf_values=None, crash=False):
    run_dir = root / "run"
    run_dir.mkdir(parents=True)
    extracted = [
        {"id": "r1", "source_file": "a.json"},
        {"id": "r2", "source_file": "a.json"},
        {"id": "r3", "source_file": "b.json"},
    ]
    validated = extracted[:2]
    issues = [
        {"severity": "error", "code": "MISSING_ID"},
        {"severity": "warn", "code": "MISSING_MATERIAL"},
    ]
    (run_dir / "01-extracted.jsonl").write_text(
        "\n".join(json.dumps(r) for r in extracted), encoding="utf-8"
    )
    (run_dir / "02-validated.jsonl").write_text(
        "\n".join(json.dumps(r) for r in validated), encoding="utf-8"
    )
    (run_dir / "02-issues.jsonl").write_text(
        "\n".join(json.dumps(r) for r in issues), encoding="utf-8"
    )
    meta = {
        "run_id": "test-run",
        "status": "completed",
        "elapsed_seconds": 0.5,
    }
    if crash:
        # 基线崩溃场景：transform 未产出，meta 记录失败前的阶段
        meta = {"run_id": "test-run", "status": "crashed"}
    else:
        meta["status"] = "completed"
    (run_dir / "run-meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if transformed and not crash:
        conf_values = conf_values or ["high", "medium", None]
        recs = [
            {"material_name": "U-10Mo" if i == 0 else None,
             "material_formula": "U10Mo" if i == 0 else None,
             "confidence": c}
            for i, c in enumerate(conf_values)
        ]
        (run_dir / "03-transformed.jsonl").write_text(
            "\n".join(json.dumps(r) for r in recs), encoding="utf-8"
        )
    return run_dir


def test_collect_metrics_full_run(tmp_path):
    run_dir = _write_run(tmp_path)
    m = collect_metrics(str(run_dir))
    assert m["records_extracted"] == 3
    assert m["records_valid"] == 2
    assert m["records_error"] == 1
    assert m["validation_pass_rate"] == round(2 / 3, 4)
    assert m["top_issue_codes"]["error:MISSING_ID"] == 1
    assert m["confidence_distribution"] == {"high": 1, "medium": 1, "missing": 1}
    assert m["confidence_coverage"] == round(2 / 3, 4)
    assert m["material_resolved"] == 1
    assert m["material_formula_matched"] == 1


def test_collect_metrics_crashed_baseline(tmp_path):
    run_dir = _write_run(tmp_path, transformed=False, crash=True)
    m = collect_metrics(str(run_dir))
    # 校验阶段指标可用，transform 指标降级为 None
    assert m["records_valid"] == 2
    assert m["confidence_distribution"] is None
    assert m["material_resolved"] is None


def test_render_markdown_contains_both_columns(tmp_path):
    b = collect_metrics(str(_write_run(tmp_path / "b", transformed=False, crash=True)))
    c = collect_metrics(str(_write_run(tmp_path / "c")))
    md = render_markdown(b, c, "baseline", "current", "T")
    assert "| 指标 | 基线 | 当前 |" in md
    assert "N/A" in md  # 基线缺失项
    assert "error:MISSING_ID" in md
