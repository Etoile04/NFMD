"""版本对比分析（NFMA-8）：从两次 dry-run 管线产物统一统计指标。

读取 run 目录（01-extracted / 02-validated / 02-issues / 03-transformed /
04-load-summary / run-meta），输出机器可读 JSON 与 Markdown 对比报告。
基线版本产物可能缺失 03/04（如 transform 阶段崩溃），指标按可得性降级。

用法::

    uv run python -m etl.compare_runs \\
        --baseline data/comparison/runs-baseline/batch-baseline \\
        --current data/comparison/runs-current/batch-current \\
        --out-md docs/acceptance/version-comparison-sample.md
"""

import argparse
import json
import os
import time

from etl.io_utils import write_json
from etl.logging_config import get_logger
from etl.path_safety import safe_open_read, safe_open_write, safe_read_path

logger = get_logger(__name__)


def _read_jsonl(path: str) -> list[dict]:
    path = safe_read_path(path)
    try:
        f = safe_open_read(path)
    except FileNotFoundError:
        return []
    with f:
        return [json.loads(line) for line in f if line.strip()]


def _read_meta(run_dir: str) -> dict:
    try:
        f = safe_open_read(safe_read_path(f"{run_dir}/run-meta.json"))
    except FileNotFoundError:
        # 崩溃的 run 可能未写出 meta
        return {}
    with f:
        return json.load(f)


def collect_metrics(run_dir: str) -> dict:
    """从单个 run 目录统计指标；缺失的阶段标记为 None。"""
    run_dir = safe_read_path(run_dir)
    meta = _read_meta(run_dir)
    extracted = _read_jsonl(f"{run_dir}/01-extracted.jsonl")
    validated = _read_jsonl(f"{run_dir}/02-validated.jsonl")
    issues = _read_jsonl(f"{run_dir}/02-issues.jsonl")
    transformed = _read_jsonl(f"{run_dir}/03-transformed.jsonl")

    has_transform = len(transformed) > 0 or "03-transformed.jsonl" in _list_run(run_dir)
    # 基线崩溃 run（无 run-meta）以 CRASHED.md 标记，见 NFMA-8 对比数据集
    status = meta.get("status") or (
        "crashed" if "CRASHED.md" in _list_run(run_dir) else None
    )
    n_extracted = len(extracted)
    n_valid = len(validated)

    issue_codes: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for iss in issues:
        key = f"{iss.get('severity', '?')}:{iss.get('code', '?')}"
        issue_codes[key] = issue_codes.get(key, 0) + 1
        sev = iss.get("severity", "?")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    metrics = {
        "run_dir": run_dir,
        "run_id": meta.get("run_id"),
        "status": status,
        "elapsed_seconds": meta.get("elapsed_seconds"),
        "source_files": len({r.get("source_file") for r in extracted}),
        "records_extracted": n_extracted,
        "records_valid": n_valid,
        "records_error": n_extracted - n_valid,
        "validation_pass_rate": round(n_valid / n_extracted, 4) if n_extracted else None,
        "severity_counts": severity_counts,
        "top_issue_codes": dict(sorted(issue_codes.items(), key=lambda x: -x[1])[:15]),
    }

    if has_transform:
        conf: dict[str, int] = {}
        for t in transformed:
            label = t.get("confidence") or "missing"
            conf[label] = conf.get(label, 0) + 1
        metrics.update(
            {
                "confidence_distribution": dict(
                    sorted(conf.items(), key=lambda x: -x[1])
                ),
                "confidence_coverage": round(
                    sum(v for k, v in conf.items() if k != "missing") / len(transformed), 4
                )
                if transformed
                else None,
                "material_resolved": sum(1 for t in transformed if t.get("material_name")),
                "material_formula_matched": sum(
                    1 for t in transformed if t.get("material_formula")
                ),
            }
        )
    else:
        metrics.update(
            {
                "confidence_distribution": None,
                "confidence_coverage": None,
                "material_resolved": None,
                "material_formula_matched": None,
            }
        )
    return metrics


def _list_run(run_dir: str) -> list[str]:
    return os.listdir(run_dir) if os.path.isdir(run_dir) else []


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.4f}" if v < 1 else f"{v:g}"
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def render_markdown(
    baseline: dict, current: dict, baseline_label: str, current_label: str, title: str
) -> str:
    """渲染两版本指标对比 Markdown。"""
    rows = [
        ("运行状态", "status"),
        ("运行时长 (s)", "elapsed_seconds"),
        ("源文件数", "source_files"),
        ("抽取记录", "records_extracted"),
        ("校验通过", "records_valid"),
        ("校验失败 (error)", "records_error"),
        ("校验通过率", "validation_pass_rate"),
        ("confidence 覆盖率", "confidence_coverage"),
        ("confidence 分布", "confidence_distribution"),
        ("材料解析 (material_name)", "material_resolved"),
        ("化学式匹配 (material_formula)", "material_formula_matched"),
    ]
    lines = [f"# {title}", ""]
    lines.append(f"- 基线：`{baseline_label}`")
    lines.append(f"- 当前：`{current_label}`")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("| 指标 | 基线 | 当前 |")
    lines.append("|---|---|---|")
    for label, key in rows:
        lines.append(f"| {label} | {_fmt(baseline.get(key))} | {_fmt(current.get(key))} |")
    lines.append("")
    lines.append("## 告警码对比（severity:code）")
    lines.append("")
    b_codes = baseline.get("top_issue_codes") or {}
    c_codes = current.get("top_issue_codes") or {}
    codes = sorted(
        set(b_codes) | set(c_codes),
        key=lambda c: -(b_codes.get(c, 0) + c_codes.get(c, 0)),
    )
    lines.append("| 告警码 | 基线 | 当前 |")
    lines.append("|---|---|---|")
    for c in codes:
        lines.append(
            f"| {c} | {b_codes.get(c, 'N/A')} | {c_codes.get(c, 'N/A')} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="NFMD 版本对比分析 (NFMA-8)")
    parser.add_argument("--baseline", required=True, help="基线 run 目录")
    parser.add_argument("--current", required=True, help="当前 run 目录")
    parser.add_argument("--baseline-label", default=None)
    parser.add_argument("--current-label", default=None)
    parser.add_argument("--title", default="ETL 版本对比报告")
    parser.add_argument("--out-md", default=None)
    parser.add_argument("--out-json", default=None)
    args = parser.parse_args()

    baseline = collect_metrics(args.baseline)
    current = collect_metrics(args.current)
    payload = {
        "baseline_label": args.baseline_label or args.baseline,
        "current_label": args.current_label or args.current,
        "baseline": baseline,
        "current": current,
    }
    if args.out_json:
        write_json(args.out_json, payload)
        logger.info("JSON 指标写入 %s", args.out_json)
    md = render_markdown(
        baseline,
        current,
        payload["baseline_label"],
        payload["current_label"],
        args.title,
    )
    if args.out_md:
        with safe_open_write(args.out_md) as f:
            f.write(md)
        logger.info("Markdown 报告写入 %s", args.out_md)
    else:
        print(md)


if __name__ == "__main__":
    main()
