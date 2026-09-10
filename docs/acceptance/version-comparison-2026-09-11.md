# 测试报告 — 升级前后 ETL 性能对比（NFMA-8，NFMA-1 follow-up）

- 日期：2026-09-11
- 基线版本：`f730210`（升级前，NFMA-1 ETL 升级之前）
- 当前版本：`bb34853`（当前 main）
- 语料：`fuel_swelling_wiki/parameters` 全量快照 458 文件（469 引用）+ 确定性抽样 30 文件（清单 `data/comparison/sample-manifest.json`，抽样见 `data/comparison/sample/`）
- 运行方式：两版本各自 checkout（基线经 git worktree），`python -m etl.run_pipeline --mode dry-run`，产物存 `data/comparison/runs-{baseline,current}/`
- 分析工具：`python -m etl.compare_runs`（单测 `scripts/etl/tests/test_compare_runs.py`）
- 详细机器可读对比：[version-comparison-sample.md](version-comparison-sample.md)（30 文件样本）、[version-comparison-full.md](version-comparison-full.md)（全量语料）、`data/comparison/version-comparison-{sample,full}.json`

## 结论

1. **正确性回归：无。** 两版本在抽取、校验阶段逐条一致（全量 14,740 条抽取 / 14,319 通过 / 421 error，告警码分布完全相同）；样本上 confidence 分布与材料解析也完全一致。
2. **基线在全量语料上无法完成 dry-run**：Stage 3 transform 崩溃——`_normalize_confidence` 对语料中的数值型 confidence（float）抛 `AttributeError: 'float' object has no attribute 'lower'`（30 文件样本恰好不含数值 confidence，因此样本可跑通）。当前版本由 ChatExtract confidence 判据（d3a52c6，NFMA-2）修复，数值分归一为 high/medium/low。基线崩溃现场见 `data/comparison/runs-baseline/full-baseline/CRASHED.md`。
3. **当前版本新增能力（样本实测）**：pymatgen 化学式归一新增 `material_formula` 匹配 61/837 条（全量 1,707/14,319）；数值 confidence 归一使全量 confidence 覆盖率 99.38%（基线无法产出）。
4. **告警码变化**：基线的 `warn:INVALID_CONFIDENCE`（452 条，全量）在当前版本消失——数值 confidence 不再判无效，被正确归一。
5. **运行时长**：全量语料当前版本 dry-run 0.7 s（14,740 条）；样本 0.2 s vs 基线 0.0 s——新增 formula/confidence 处理的耗时开销在亚秒级，可忽略。基线无全量时长（崩溃前未计时）。

## 指标速览

| 指标（全量 458 文件） | f730210 基线 | bb34853 当前 |
|---|---|---|
| 运行状态 | **crashed（Stage 3）** | completed |
| 抽取 / 校验通过 / error | 14,740 / 14,319 / 421 | 14,740 / 14,319 / 421 |
| 校验通过率 | 97.14% | 97.14% |
| confidence 覆盖率 | N/A（崩溃） | 99.38% |
| 材料解析 / 化学式匹配 | N/A（崩溃） | 8,073 / 1,707 |
| 运行时长 | N/A | 0.7 s |

## 复现

```bash
# 基线（worktree）
git worktree add /tmp/nfmd-baseline f730210
cd /tmp/nfmd-baseline && PYTHONPATH=scripts python -m etl.run_pipeline --mode dry-run \
  --source-dir <repo>/data/comparison/corpus-snapshot        # → Stage 3 崩溃
# 当前
python -m etl.run_pipeline --mode dry-run --source-dir data/comparison/corpus-snapshot
# 对比
python -m etl.compare_runs --baseline <run-a> --current <run-b> --out-md report.md
```
