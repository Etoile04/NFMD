# Parameters 表 schema 差距走查 — NEMAD / PIF 对标（NFMA-10）

- 日期：2026-09-11
- 性质：纯文档走查（调研报告 §5 短期项 2：拿 NEMAD 条目 schema 与 PIF 条件树对照 `plans/schema_v2.sql` 的 parameters 表，输出差距清单，为 schema 演进立项——**本走查不改任何 schema**）
- 证据基础：全文试点（[report.md](../acceptance/fulltext-pilot-2026-09-11/report.md)）与独立会话复测（[independent-retest.md](../acceptance/fulltext-pilot-2026-09-11/independent-retest.md)）
- 对标参照：调研报告 §4.1.4（NEMAD，Itani et al., Nat Commun 2025）与 §4.3.1（PIF，Citrine，已归档只借思想）

## 1. 走查结论总表

| # | 差距 | 现状（schema_v2） | NEMAD/PIF 对应做法 | 试点/复测证据 | 优先级 |
|---|------|------------------|-------------------|--------------|--------|
| G1 | 值-单位受控词表 | `unit text` 自由串；business key 含 unit，无规范 | NEMAD 平铺字段各带固定单位语义 | 宽松/严格口径差 22pp；复测 113 个值级匹配对中 24 对（21%）单位归一后仍不同 | **P0**（ETL 侧已落地 v2，激活需回填） |
| G2 | 不确定度结构化 | `uncertainty text`（如 "±50%"） | NEMAD 无此字段；PIF 以精确度属性承载 | 金标把 `11.7±0.2` 存成 range `[11.7, 0.2]`——±形与区间形语义混用 | **P0**（ADR-0006 决策候选） |
| G3 | 条件组表达 | `temperature_k` 单列 + `burnup_range text`；多条件（温度×燃耗×注量）无组合结构 | PIF 条件树：同一性质多条件分支以树共存，每支带 provenance | jnpe_2025 的 dpa/rpa 等效深度是「材料×离子×能量」三条件函数，只能拆成 8 条独立记录靠 name 编码条件 | P1（ADR-0007 候选） |
| G4 | 来源链 provenance | `source_file` + `audit_log`（只记参数变更前后值） | NEMAD 每条目带来源引用；PIF 每分支带 provenance | 试点/复测的 channel_a/b/self_audit 证据字段在入库后无落点，confidence 推导链不可回溯 | P1（ADR-0007 候选） |
| G5 | literature 元数据 | 有 `doi`；无 `license` | FAIR Reusable 要求 | 调研报告 §4.3.6 已列为 schema 变更项 | P2 |
| G6 | 量纲前缀单位 | `×10⁻⁶/K`、`×10²¹ fissions/cm³` 一类「值内含数量级」的单位串进 unit 列 | — | `dpa/10^-15 cm^-2` 这类复合形无法机械归一（值与前缀耦合） | P2（随 G1 词表扩容渐进） |

## 2. 各差距展开

### G1/G2（本轮立项，ADR-0006）

试点差异归因的第一主因即 G1：金标单位用 Unicode 漂串（`10⁻¹⁵ cm⁻²`、`W/(cm*K)`），抽取用 ASCII（`10^15 cm^-2`、`W/cm-C`）。ETL 侧受控词表 v2（`etl.normalize`：`^` 指数折叠 + `*`→`·` 分隔符统一 + 扩容别名表）已随 NFMA-10 落地并带测试；**激活它改变后续 load 的 business key（unit 分量），存量 17k 行需要回填**，属 🟡 需人工批准（流程与草案 SQL 见 [ADR-0006](../adr/0006-unit-vocabulary-and-uncertainty-split.md)）。

G2 是同一证据的另一面：`±` 形不确定度被迫挤进 range 型值（`[11.7, 0.2]`），污染了 value_type 语义与 business key。ADR-0006 决策候选二即 `uncertainty_value` 分列（可空、append-safe）。

### G3 条件组（暂缓，先记录模式）

PIF 的条件树在 NFMD 的平铺 schema 上有不破坏兼容的近似表达：以 `value_list` 承载 (条件, 值) 对 + `conditions` 文本列。但试点语料里更常见的形态是「同一物理量在不同条件下的多条记录」（如 Table 3 的 8 行等效深度），name 编码条件已经够用；真正的痛点（跨条件查询）应由 API 层过滤解决。**结论：暂缓 schema 改动，等 API 消费场景出现真实查询需求再立项。**

### G4 provenance（暂缓，方向已明）

理想形态（参照 AiiDA 实体-链接）：`literature → extract_run（含模型/协议/prompt 版本）→ 参数版本`。试点的 `channel_a/channel_b/self_audit` 证据字段目前只在语料 JSON 里，dry-run 验收后即丢失。低成本过渡：把这些证据收进 `parameters.notes`（JSON 前缀）即可回溯，不动 schema；正式 provenance 链等 ADR-0007。

### G5/G6

`literature.license` 是 FAIR 检查表缺口，一行可空列，随下一次 🟡 批量一起做。量纲前缀单位（G6）无法完全机械归一，词表按证据渐进扩容即可，不单独立项。

## 3. 建议

1. **本轮只推 G1+G2**（ADR-0006，Draft 待 CPO 评审）：单位词表激活回填 + uncertainty 分列，一次 🟡 流程做完。
2. G3/G4 记为 ADR-0007 候选，触发条件：API 出现跨条件查询需求 / 下游（燃料性能程序）开始质疑参数来源。
3. G5 随下一批 schema 变更捎带；G6 随 G1 词表渐进。
