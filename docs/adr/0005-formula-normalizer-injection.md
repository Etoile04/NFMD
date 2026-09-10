# ADR-0005: FormulaNormalizer 接口注入 normalize 阶段（pymatgen 走 optional extras）

- 状态：**Draft（待 CPO 评审）**
- 日期：2026-09-11
- 关联：[ADR-0002](0002-dependencies-accepted-not-created.md)（依赖接受原则）、NFMA-2、调研报告 §4（pymatgen 条目）

## 背景

调研报告（docs/research/ai-infrastructure-for-materials-discovery-survey.md）将 pymatgen 评为"直接引入"：`Composition` 可承担 normalize 阶段化学式解析/校验（UO2、U3Si2 一类写法），补 alias map 之外的机械归一。ADR-0002 确立"依赖是被接受进来的，不是被顺手创建的"——pymatgen 依赖面较重，必须显式决策其引入形态。

## 决策（候选）

1. pymatgen 以 **optional extras** 进入仓库：`uv sync --extra chem`（`[project.optional-dependencies].chem`），不是核心依赖。
2. normalize 阶段新增 **FormulaNormalizer 接口**（`etl.formula.FormulaNormalizer` Protocol + `FormulaResult`），由 `build_formula_normalizer()` 工厂构建并**注入** `transform_records(records, material_norm, formula_norm=None)`。
3. pymatgen 实现位于 extras 路径 `etl.formula_pymatgen`（顶层 import pymatgen）；extras 缺失时工厂降级为 stdlib `RegexFormulaNormalizer`（只认纯化学计量式）并 log warning——**无 pymatgen 环境下 ETL 完整可运行**。
4. 归一结果写 `TransformedRecord.material_formula`；解析失败（合金 wt.%、非计量式 UO2+x、自由文本）返回 matched=False，留给 alias map 语义归一，不视为错误。

## 后果

- 依赖面：核心 `uv.lock` 不含 pymatgen；需要完整化学式引擎的环境显式 `uv sync --extra chem`。
- 测试：降级行为有单测覆盖（mock pymatgen 缺失）；pymatgen 路径单测以 `pytest.importorskip` 守卫，在装有 extras 的环境自动生效。
- 风险：两引擎行为差异（regex 只做结构校验，pymatgen 做 reduced formula）；报告与 dry-run 输出携带 `formula_engine` 以便溯源。

## 待 CPO 裁决

- 是否接受 pymatgen 以 extras 形态进仓库（本 ADR 的核心问题）。
- extras 命名 `chem` 是否合适。
