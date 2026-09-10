# 版本对比 — 全量语料（458 文件）dry-run

- 基线：`f730210（升级前基线）· 全量语料 458 文件（Stage 3 transform 崩溃，见 CRASHED.md）`
- 当前：`bb34853（当前 main）· 全量语料 458 文件`
- 生成时间：2026-09-11 07:35

| 指标 | 基线 | 当前 |
|---|---|---|
| 运行状态 | crashed | completed |
| 运行时长 (s) | N/A | 0.7000 |
| 源文件数 | 469 | 469 |
| 抽取记录 | 14740 | 14740 |
| 校验通过 | 14319 | 14319 |
| 校验失败 (error) | 421 | 421 |
| 校验通过率 | 0.9714 | 0.9714 |
| confidence 覆盖率 | N/A | 0.9938 |
| confidence 分布 | N/A | {"high": 10254, "medium": 3741, "low": 235, "missing": 89} |
| 材料解析 (material_name) | N/A | 8073 |
| 化学式匹配 (material_formula) | N/A | 1707 |

## 告警码对比（severity:code）

| 告警码 | 基线 | 当前 |
|---|---|---|
| warn:MISSING_MATERIAL | 4251 | 4251 |
| warn:INVALID_CATEGORY | 1919 | 1919 |
| warn:INVALID_CONFIDENCE | 452 | N/A |
| error:INVALID_VALUE_TYPE | 171 | 171 |
| error:VALUE_TYPE_MISMATCH | 115 | 115 |
| error:GENERIC_NAME | 113 | 113 |
| error:SCALAR_NO_VALUE | 44 | 44 |
| error:LIST_NO_VALUES | 38 | 38 |
| error:EXPR_NO_FORMULA | 28 | 28 |
| error:RANGE_MIN_MAX_INVERTED | 16 | 16 |
| error:MISSING_VALUE_TYPE | 6 | 6 |
| error:MISSING_NAME | 6 | 6 |
| error:MISSING_ID | 6 | 6 |
| error:MISSING_CATEGORY | 6 | 6 |
