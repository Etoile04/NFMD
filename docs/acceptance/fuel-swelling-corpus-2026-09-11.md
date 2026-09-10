# 真实语料验收报告 — fuel_swelling_wiki parameters（NFMA-2）

- 日期：2026-09-11
- 语料：`~/.openclaw/workspace/data/fuel_swelling_wiki/parameters`（458 个 DOI 参数文件；记录内 `source_file` 去重为 469 个原始引用）
- 工具：`uv run python -m etl.acceptance --source-dir <corpus>`
- 机器可读报告：[fuel-swelling-corpus-2026-09-11.json](fuel-swelling-corpus-2026-09-11.json)

## 结果（dry-run，不写生产库）

| 指标 | 值 |
|---|---|
| 抽取记录 | 14,740 |
| 校验通过 | 14,319 |
| 校验失败（error 级） | 421 |
| fatal | 0 |
| 成功率 | **97.14%** |
| 验收门 | **通过**（gate_passed=true） |

### confidence 分布（ChatExtract 判据 + 0-1 数值分映射）

| high | medium | low | missing |
|---|---|---|---|
| 10,254 | 3,741 | 235 | 89 |

语料为历史抽取，尚无 `channel_a/channel_b/self_audit` 双通道元数据，confidence 来自自带标签/数值分的归一化；双通道推导规则已在单测覆盖（`scripts/etl/tests/test_confidence.py`），待上游 llm-wiki 采用 `etl.prompts` 模板后生效。

### FormulaNormalizer

- pymatgen 引擎（`etl[chem]` extras）：material_formula 匹配 1,707 条，alias map 语义归一 8,073 条。
- 无 pymatgen 环境实测：降级为 stdlib 正则引擎，ETL 完整运行、验收门同样通过（warning 一条，`formula_engine=regex`）。

### 主要 error 级问题

INVALID_VALUE_TYPE 171、VALUE_TYPE_MISMATCH 115、GENERIC_NAME 113、SCALAR_NO_VALUE 44、LIST_NO_VALUES 38、EXPR_NO_FORMULA 28、RANGE_MIN_MAX_INVERTED 16、缺 ID/NAME/CATEGORY/VALUE_TYPE 各 6。
