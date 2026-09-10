# 版本对比 — 固定样本（30 文件）dry-run

- 基线：`f730210（升级前基线）· 30 文件确定性样本`
- 当前：`bb34853（当前 main）· 30 文件确定性样本`
- 生成时间：2026-09-11 07:34

| 指标 | 基线 | 当前 |
|---|---|---|
| 运行状态 | completed | completed |
| 运行时长 (s) | 0.0000 | 0.2000 |
| 源文件数 | 29 | 29 |
| 抽取记录 | 841 | 841 |
| 校验通过 | 837 | 837 |
| 校验失败 (error) | 4 | 4 |
| 校验通过率 | 0.9952 | 0.9952 |
| confidence 覆盖率 | 1 | 1 |
| confidence 分布 | {"high": 530, "medium": 286, "low": 21} | {"high": 530, "medium": 286, "low": 21} |
| 材料解析 (material_name) | 346 | 346 |
| 化学式匹配 (material_formula) | 0 | 61 |

## 告警码对比（severity:code）

| 告警码 | 基线 | 当前 |
|---|---|---|
| warn:MISSING_MATERIAL | 280 | 280 |
| warn:INVALID_CATEGORY | 154 | 154 |
| error:VALUE_TYPE_MISMATCH | 3 | 3 |
| error:LIST_NO_VALUES | 3 | 3 |
| error:RANGE_MIN_MAX_INVERTED | 1 | 1 |
