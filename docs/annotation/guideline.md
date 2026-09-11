# 标注规范（v1）— NFMD 人工专家金标

适用工具：`uv run python -m etl.annotate`（自建轻量标注器，见 `scripts/etl/annotate.py`）。
本规范定义「一条参数记录」的判定口径、字段填法与歧义裁决，供标注人（专家）与仲裁人使用。
字段命名与 ETL 数据域一致（`CONTEXT.md`、`etl.models.ExtractedRecord`）。

## 1. 什么算一条参数（收录判据）

- **收录**：原文以数值/区间/表达式形式**明确报告**的量（正文、表格、图注中的印出数值）。
- **不收录**：
  - 仅图上估读、未印数值的读数（除非图上印有数值）；
  - 作者**推导或引用他人文献**的值——引用值如需保留，`notes` 标 `cited`，且不进入该论文金标的独立条目；
  - 纯背景叙述、无量纲叙述性描述（如 "significant swelling was observed"）。
- 一条记录 = 一个（材料, 参数名, 条件）组合下的一个取值。同量多条件分别成条。

## 2. 字段口径

### 2.1 名称与分类
- `name_en`：具体物理量英文名（如 `displacement threshold energy of U in SRIM calculation`）。禁止泛称（`parameter`、`肿胀参数` 等会被 `GENERIC_NAME` 规则拒绝）。
- `category`：只能取 `scripts/etl/rules.py::VALID_CATEGORIES`（标注器下拉限定）。

### 2.2 值与类型
- `value_type` 五选一，判定示例（取自试点真实记录）：
  - `scalar`：单数值，如 displacement threshold energy of U = `35.6` eV；
  - `range`：区间，填 `value_min` / `value_max`（如肿胀量 0.7–5.2 %）；
  - `expression`：公式/拟合式（填 `value_expr` 或 `equation`）；
  - `list`：成组离散值（如同一条中并列的多个应变率）；
  - `text`：非数值取值，如 `"1000's of dpa"`（试点记录 10_1063_1_5127696_01）。
- **不确定度**：`±` 形一律写 `uncertainty` 字段，**禁止**把 `±x` 挤进 range 的 min/max（ADR-0006 的根因）。
- **单位双列**：`unit` 原文照录（含 µ/μ、上标等）；`unit_canonical` 由 `normalize_unit` 自动预填，标注人可改。

### 2.3 条件归属
- temperature / burnup 有**明确数值**时进 `temperature_K` / `burnup` 字段（非开尔文温度照录原值 + 原单位进 notes，换算由管线完成）；
- 仅叙述性条件（如 "under irradiation at high temperature"）进 `conditions` / `notes`，不进数值字段。

### 2.4 材料
- 优先取 `plans/material-alias-map.json` 的 `canonical_name`；查不到则按论文原文英文照录，不做意译。

### 2.5 出处
- 每条必附 `source_sentence`（≤2 句原文引用，标注器划选自动填充）+ `source_location`（页码/章节/表号）。

## 3. 双人标注与仲裁流程

1. 两位标注人独立在各自子目录（`<out>/<annotator>/<slug>.json`）完成同一 slug；
2. 仲裁视图并排两侧记录，值级自动比对（`fulltext_pilot.values_match`，2% 相对容差）；
3. 仲裁人对每对：一致 → 任选一侧；不一致/单侧 → 人工裁决取正确者或合并修正；
4. 合并结果导出 `gold/<slug>.json`，可直接被 `fulltext_pilot.evaluate_against_gold` 消费；
5. 一致性统计（值级匹配率）作为过程质量指标记录，不设硬门槛。

## 4. 试点歧义案例（裁决口径）

1. **引用值 vs 自报值**（10_1063_1_5127696）：文中转述他人测得的扩散系数——不标独立条目；确需保留时 `notes: cited`。
2. **"1000's of dpa"**（同上）：数量级叙述而非精确值 → `value_type=text`，unit=dpa；不臆造 scalar 1000。
3. **± 不确定度误入 range**：试点对照中出现过 `±0.3` 被折叠成 range [x−0.3, x+0.3] 的案例——金标必须 center 值为 scalar + `uncertainty="0.3"`。
4. **SRIM 输入参数算不算**（10_13832_j_jnpe_2025_S2_0122）：`displacement threshold energy` 是模拟输入而非实测物性——**收录**（NFMD 收 simulation_parameter），`category=simulation_parameter`，notes 注明 `SRIM input`。
5. **条件归属**： swelling "at 350–650 °C" → temperature 数值化进条件字段；"under neutron irradiation" 无数值 → conditions 字段。
