# ADR-0006: 单位受控词表激活 + uncertainty 分列（schema v3 草案）

- 状态：**Accepted（CPO 裁决 2026-09-12，见文末裁决记录）**
- 日期：2026-09-11
- 关联：[ADR-0002](0002-dependencies-accepted-not-created.md)、[ADR-0005](0005-formula-normalizer-injection.md)、[docs/database-safety-rules.md](../database-safety-rules.md)、[gap 走查](../research/parameters-schema-gap-walkthrough.md)（G1/G2）、NFMA-9 试点与 NFMA-10 复测证据

## 背景

全文试点与独立会话复测给出了同一定量证据：**值级匹配中约 21% 的损失来自单位串序列化异构**（`W/(cm*K)` vs `W/cm-C`、`10⁻¹⁵ cm⁻²` vs `10^15 cm^-2`），宽松/严格口径差 22 个百分点。根因是 parameters 的 business key 含 `unit` 而单位无受控词表；次因是 `±` 形不确定度被挤进 range 型值（金标 `11.7±0.2` → `[11.7, 0.2]`），污染 value_type 语义。

NFMA-10 已在 ETL 侧落地词表 v2（`etl.normalize`：`^` 指数折叠、`*`→`·` 分隔符统一、两层别名查找，测试覆盖试点观察到的全部异构形态）。本 ADR 决策其**激活方式**与 uncertainty 的 schema 演进。

## 决策（候选）

### D1 — 单位词表激活：回填存量 unit，属 🟡 需人工批准

词表只影响新 load 的 business key；不回填则同一参数会以新旧两种 unit 串并存（business key 失配 → 近重复行）。回填仅限**能被词表精确命中**的旧值（机械折叠 + 别名表，与 `etl.normalize.normalize_unit` 同一逻辑派生 CASE 链），其余原样保留。

### D2 — uncertainty 分列：可空新列，append-safe

```sql
-- 草案（未执行）。执行按 docs/database-safety-rules.md 🟡 流程：
-- COUNT 先行 → 预览 → 备份 → BEGIN…COMMIT 包裹 → 报告影响行数
ALTER TABLE parameters
    ADD COLUMN IF NOT EXISTS uncertainty_value numeric(20,10),  -- 不确定度数值（与 value 同单位）
    ADD COLUMN IF NOT EXISTS uncertainty_kind  text;            -- absolute / relative_pct
-- 旧列 uncertainty (text) 保留，作为历史兼容与自由文本兜底；约束：
ALTER TABLE parameters ADD CONSTRAINT chk_params_uncertainty CHECK (
    uncertainty_value IS NULL OR uncertainty_value >= 0
);
```

配套 ETL 语义（`etl.transform` 侧，无需 schema 之外的改动）：

- 抽取侧 `±` 形（如 `11.7±0.2`）解析为 `value_scalar=11.7, uncertainty_value=0.2, uncertainty_kind='absolute'`，**不再生成 range 型记录**；
- `±x%` 形解析为 `uncertainty_kind='relative_pct'`；
- 既有 range `[值, 不确定度]` 形（试点口径识别：`|b| ≤ 5%|a|`）在回扫时迁为标量+不确定度——此迁移影响存量行，并入 D1 的同一 🟡 流程执行。

### D3 — 明确暂缓项

条件组（G3）、provenance 链（G4）、`literature.license`（G5）不在本 ADR 范围（走查结论：ADR-0007 候选 / 随下一批捎带）。

## 后果

- **正向**：business key 的 unit 分量获得稳定规范形，跨来源抽取的同参数可正确去重；±形不确定度不再污染 value_type。
- **成本/风险**：回填触及存量 `parameters`（预计数百行量级——精确命中词表的旧串子集，执行前 COUNT 确认）；触发 `trg_params_audit` 与 tsvector 重算（逐行 UPDATE，事务内可控）。
- **兼容性**：新列一律可空，旧 `uncertainty text` 列保留——API 读取路径（`etl.api`）无需变更即可继续工作；下游消费新列属增强。
- **不触红线**：无 DROP/TRUNCATE/无 WHERE 的 DELETE；全部变更走事务 + 行数报告。

## 待 CPO 裁决

1. 是否批准 D1 回填（执行窗口 + 备份位置确认）；
2. 是否批准 D2 的两列形态（vs. 单列 `numeric` + 隐式绝对语义）；
3. 回填映射是否要求人工抽查清单（建议：回填前导出 distinct 旧值 → 新值映射表供抽查）。

## CPO 裁决记录（2026-09-12）

ADR-0006 整体批准（D1/D2/D3 全部通过），附加执行条件：

1. **D1 回填：批准**。附加条件：(a) 执行前导出 distinct 旧 unit 串 → 新规范形的完整映射表（人工抽查后再执行）；(b) `pg_dump parameters` 全表备份落 `var/backups/parameters-pre-v3-<date>.sql.gz`；(c) 按 🟡 流程 COUNT → 预览 → 备份 → 事务包裹 → 行数报告。执行窗口：下次 ETL load 前，随 schema v3 迁移一并完成。
2. **D2 两列形态：批准**。`uncertainty_value` + `uncertainty_kind` 显式优于单列隐式绝对语义——`relative_pct` 已在试点语料中出现，单列方案会立刻再次欠拟合。range 迁移（`|b| ≤ 5%|a|` 判定）并入 D1 同一事务。
3. **映射抽查：要求**。distinct 映射表先于回填落地，抽查通过是回填执行的前置门（gate），不是事后审计。
4. **D3 暂缓项：确认**。G3/G4/G5 不入本批次；G3 条件组列 ADR-0007 候选，G4/G5 随下一批捎带。
