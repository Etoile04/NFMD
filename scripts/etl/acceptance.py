"""真实语料验收门（NFMA-2）：对抽取语料做 dry-run 级验收并输出报告。

不写生产库——只跑 extract → validate → transform 三阶段，汇总成功率
与 confidence 分布。用法::

    uv run python -m etl.acceptance --source-dir <corpus> [--alias-map <map>]
"""

import argparse
import json
import sys

from etl.extract import extract_records
from etl.formula import build_formula_normalizer
from etl.io_utils import write_json
from etl.logging_config import get_logger
from etl.normalize import MaterialNormalizer
from etl.transform import transform_records
from etl.validate import validate_records

logger = get_logger(__name__)

# 与 run_pipeline 的 DEFAULT_ALIAS_MAP 保持一致
DEFAULT_ALIAS_MAP = "plans/material-alias-map.json"


def run_acceptance(source_dir: str, alias_map: str) -> dict:
    """对 source_dir 语料跑三阶段 dry-run，返回验收报告 dict。"""
    records = list(extract_records(source_dir))
    valid, errored, issues = validate_records(records, run_id="acceptance")
    fatal_count = sum(1 for i in issues if i.severity == "fatal")

    mat_norm = MaterialNormalizer(alias_map)
    formula_norm = build_formula_normalizer()
    transformed = transform_records(valid, mat_norm, formula_norm)

    confidence_dist: dict[str, int] = {}
    for t in transformed:
        label = t.confidence or "missing"
        confidence_dist[label] = confidence_dist.get(label, 0) + 1

    code_counts: dict[str, int] = {}
    for iss in issues:
        key = f"{iss.severity}:{iss.code}"
        code_counts[key] = code_counts.get(key, 0) + 1

    n = len(records)
    report = {
        "source_dir": source_dir,
        "source_files": len({r.source_file for r in records}),
        "records_extracted": n,
        "records_valid": len(valid),
        "records_error": len(errored),
        "fatal_count": fatal_count,
        "success_rate": round(len(valid) / n, 4) if n else None,
        "gate_passed": n > 0 and fatal_count == 0,
        "confidence_distribution": dict(
            sorted(confidence_dist.items(), key=lambda x: -x[1])
        ),
        "formula_engine": formula_norm.engine,
        "material_resolved": sum(1 for t in transformed if t.material_name),
        "material_formula_matched": sum(
            1 for t in transformed if t.material_formula
        ),
        "top_issue_codes": dict(sorted(code_counts.items(), key=lambda x: -x[1])[:15]),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="NFMD 真实语料验收门（dry-run）")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--alias-map", default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--output", default=None, help="报告 JSON 输出路径")
    args = parser.parse_args()

    report = run_acceptance(args.source_dir, args.alias_map)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        write_json(args.output, report)
        logger.info("Report written to %s", args.output)
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
