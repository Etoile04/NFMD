# 测试报告 — 升级前后 ETL 性能对比（NFMA-8，NFMA-1 follow-up）

- 日期：2026-09-11
- 基线版本：`f730210`（升级前，NFMA-1 ETL 升级之前）
- 当前版本：`bb34853`（当前 main）
- 语料：`fuel_swelling_wiki/parameters` 全量快照 458 文件（469 引用）+ 确定性抽样 30 文件（清单见 [comparison-2026-09-11/sample-manifest.json](comparison-2026-09-11/sample-manifest.json)；抽样规则：快照文件名排序后每第 15 个）
- 运行方式：两版本各自 checkout（基线经 git worktree），`python -m etl.run_pipeline --mode dry-run`，产物存 `data/comparison/runs-{baseline,current}/`（本地）
- 分析工具：`python -m etl.compare_runs`（单测 `scripts/etl/tests/test_compare_runs.py`）
- 详细机器可读对比：[version-comparison-sample.md](version-comparison-sample.md)（30 文件样本）、[version-comparison-full.md](version-comparison-full.md)（全量语料）、指标数据集 [comparison-2026-09-11/{batch,full}-metrics.json](comparison-2026-09-11/)

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

## 逐篇实测明细（30 文件样本）

两版本的抽取/校验/解析/confidence 在每篇文献上**逐条一致**（行为保持的直接证据）；差异仅出现在最后一列——当前版本新增的 `material_formula` 化学式匹配数（基线恒为 0）。解析率/material_name 两版本相同，故只列一列。

| 文献（source_file 摘要） | 记录 | 解析率 | conf 覆盖 | formula（当前版新增） |
|---|---|---|---|---|
| 10_1680_ieacifcacc_48748 | 16 | 0% | 100% | 0 |
| 2001_Ravishankar_EffectivePotentialAgCu | 3 | 0% | 100% | 0 |
| 2010_Gan_Transmissionelectro | 82 | 38% | 100% | 1 |
| 2013_Kim_UMoalloyfuelforTRUburnin | 25 | 16% | 100% | 0 |
| 2015_Rabin_FOURPOINTBENDTESTINGOFIRR | 24 | 42% | 100% | 0 |
| 2016_Säubert_NeutronandhardXr | 42 | 0% | 100% | 0 |
| 2018_Devaraj_Grainboundaryengin | 40 | 50% | 100% | 0 |
| 2018_Starikov_Atomisticsimulation | 24 | 92% | 100% | 0 |
| 2019_Miao_Anexplorationofme | 7 | 43% | 100% | 2 |
| 2020_Hirschhorn_UZr_DiffusionCouple_PF | 13 | 100% | 100% | 0 |
| 2021_Beeler_Radiationdrivendif | 19 | 79% | 100% | 0 |
| 2022_Aagesen_PFBubbleInterconnection | 29 | 100% | 100% | 0 |
| 2022_Sun_Unveilingtheintera | 43 | 100% | 100% | **43** |
| 2023_Ke_MicrostructureModeling | 36 | 39% | 100% | 7 |
| 2023_Tian_Moleculardynamicssimulation | 28 | 29% | 100% | 0 |
| 2024_Kim_ThermalConductivityUMo | 1 | 100% | 100% | 0 |
| 2025_Doyle_SwellingandFission | 21 | 95% | 100% | 0 |
| 2025_Pizzocri_MultiFidelity_FuelPerformance | 8 | 100% | 100% | **8** |
| 2026_Fay_3DPoreReconstruction_Fluff_EBR2 | 12 | 100% | 100% | 0 |
| Evidence of Xe-incorporation … U-Mo fuel | 32 | 0% | 100% | 0 |
| R.M. WILLARD 1985 U-10 wt% 系 | 42 | 57% | 100% | 0 |
| Smith et al. 2023 UC inclusions | 11 | 0% | 100% | 0 |
| Yun 等 U-10Zr meta | 30 | 100% | 100% | 0 |
| kim_hofman_cheon_2013 U-Mo | 23 | 0% | 100% | 0 |
| raw/mineru/10_1016_j_jnucmat_2010_04_016 | 53 | 0% | 100% | 0 |
| raw/mineru/10_1016_j_jnucmat_2017_07_030 | 42 | 0% | 100% | 0 |
| raw/mineru/10_1016_j_jnucmat_2020_152441 | 51 | 0% | 100% | 0 |
| raw/mineru/10_1016_j_matchar_2020_110696 | 40 | 0% | 100% | 0 |
| raw/mineru/Aagesen 2022 U-(Pu)-Zr | 40 | 98% | 100% | 0 |
| 合计 | **837** | 41.3% | 100% | **61** |

观察：formula 增益集中在材料名以化学式书写的论文（2022_Sun 全部 43 条命中、2025_Pizzocri 8/8、2023_Ke 7）；解析率 0% 的论文（如 jnucmat DOI 系、U-Mo 燃料类）暴露的是 **alias map 词典缺口**——这正是调研报告 WP2 的目标场景（化学式机械归一），但 `material_name` 语义归一仍依赖 alias map，需按「结论 3」的路径补充词典。

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
