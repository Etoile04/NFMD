# 测试报告 — 全文级参数提取试点（NFMA-9）

- 日期：2026-09-11
- 背景：对既往对比实验语料层的核实发现，`fuel_swelling_wiki/parameters` 是历史 LLM 抽取的**产物**层；其输入（MinerU 全文 markdown，`raw/`）已从磁盘清理，但 `raw.zip`（2.0 GB，181 篇整文）、`papers/*/fulltext.txt`（25 篇）与 **Zotero 1,210 个 PDF** 均完好——全文层并非只有 summary。本试点按需从 `raw.zip` 恢复 5 篇论文全文，把「全文 → 参数」环节正式纳入测试范围。
- 分支：`NFMA-0009-fulltext-pilot`

## 方法

1. **样本**：`raw.zip` 全文 ∩ 参数金标重叠的 21 篇中，取全文最小且金标参数较多的 5 篇（15–25 KB/篇，金标 14–25 条/篇），解压恢复到规范路径 `raw/mineru/<DOI>/auto/<DOI>.md`。
2. **抽取协议**：按 `etl.prompts` 的 ChatExtract 协议（Polak et al., Nat Commun 2024）由 LLM agent 执行：通道 A 全文精读一遍、通道 B 独立第二遍（两次互不参照），逐条记录 `question` + `source_sentence` 出处；合并按问题文本归一匹配，双通道一致 → 双证据记录，单侧 → 单通道记录；自审计（self_audit）基于出处句逐条核验。产出带 `channel_a` / `channel_b` / `self_audit` 证据字段的参数 JSON（语料格式）。
3. **管线验收**：`uv run python -m etl.acceptance --source-dir <pilot>` 三阶段 dry-run（零触库）。
4. **金标对照**：值级匹配（数值相对容差 + 单位激进规范化 + `值±不确定度` 形 range 折叠）为主口径，含单位的严格口径为辅。**注意语义**：金标本身也是历史 LLM 抽取产物，指标度量的是两次独立抽取的**一致性**，不是对人工真值的精度。

## 结果

### 抽取与管线兼容性

| 指标 | 值 |
|---|---|
| 抽取记录（5 篇） | 124 |
| 双通道一致 / 单通道 | 103 / 21（**0 数值冲突**） |
| confidence 推导（ChatExtract 判据自动生效） | high 103 / medium 21 |
| ETL 校验通过 | **124/124（100%）**，0 fatal |
| 唯一告警 | warn:MISSING_MATERIAL ×19（单通道 B 记录未带材料字段） |

confidence 不再是人工标注——由双通道一致性与自审计结果**机械推导**，端到端首次在全文抽取上闭环。

### 金标对照（一致性）

| 口径 | Precision | Recall |
|---|---|---|
| 宽松（值级，±形折叠） | **0.629** | **0.812** |
| 严格（值 + 单位串） | 0.411 | 0.531 |

逐篇（宽松）：jnpe_2025 P=0.91/R=0.84；scriptamat_2015 P=0.64/R=0.95；ieacifcacc_487 P=0.45/R=0.81；1063_1_5127696 P=0.68/R=0.68；nucengdes_2018 P=0.50/R=0.79。

### 差异归因（人工核对未匹配清单）

- **序列化异构（最主要）**：金标单位用 Unicode 漂串（`10⁻¹⁵ cm⁻²`、`W/(cm*K)`、`×10²¹ fissions/cm³`），本次抽取用 ASCII（`dpa/10^15 cm^-2`、`W/cm-C`）；金标把 `11.7±0.2` 存成 range `[11.7, 0.2]`。这使严格口径比宽松低约 22 个百分点。
- **覆盖差异（次要）**：本次新抽出金标未记录的量（同步辐射 X 射线能量 71.676 keV、FIB 试样 30 μm、M316 应力组水平清单、Fig.2 临界热流 325 W/cm² 等——均经出处句核验为真）；金标亦有本次未抽的量（rpa 等效深度逐离子分列、蠕变常数全单位、对照样品燃耗 0.0 等）。
- **无一处数值矛盾**：103 组双通道一致 + 金标匹配对中未发现同量异值冲突。

## 结论与建议

1. **全文级提取测试可行且已打通**：全文 → 协议化抽取 → 证据字段 → confidence 推导 → ETL 100% 通过。语料「只有 summary、无法测试」的担忧不成立，但全文层需要维护（建议将 `raw.zip` 按需解压纳入获取流程，或以 Zotero PDF + MinerU 重建 `raw/`）。
2. **管线瓶颈在值/单位的受控词表**：business key 含 `(value, unit)`，而单位串无规范（本次宽松/严格口径差 22pp 即为其代价）。建议：单位规范化表扩容 + `值/不确定度分列`（对应调研报告的 schema 演进项，🟡 需审批）。
3. **协议有效**：双通道 + 自审计在真实全文上产出可解释的 confidence 分布（83% high），且单通道记录被正确降级为 medium。
4. **局限**：双通道由同一模型先后两个 pass 模拟（非两次独立会话），一致性可能被高估；金标是历史抽取产物，recall 低不等于错误。后续可用两套独立模型/会话复测。

## 复现

```bash
# 1) 恢复全文（按需解压）
unzip -o raw.zip "raw/mineru/<slug>/*" -x "__MACOSX/*" -d <wiki-root>/
# 2) 双通道抽取（LLM 执行，产 channelA/ channelB/ JSON）→ 合并
python3 data/fulltext-pilot/merge_channels.py          # → parameters/*.json（带证据字段）
# 3) ETL 验收（dry-run）
uv run python -m etl.acceptance --source-dir data/fulltext-pilot/parameters
# 4) 金标对照
python3 data/fulltext-pilot/eval_gold.py               # → gold-comparison.json
```

机器可读证据：[gold-comparison.json](gold-comparison.json)（逐篇 P/R 与未匹配清单）、[pilot-acceptance.json](pilot-acceptance.json)（ETL 验收）、[records/](records/)（124 条带证据字段的抽取记录）。

## 批次 2：独立会话双通道复测（2026-09-11 追加）

针对批次 1 的主要局限（双通道为同一会话先后两遍，独立性不足），批次 2 换 5 篇新论文，通道 A / 通道 B 由**两个互不可见的独立 LLM 会话**执行（每条记录带 `question` + 逐字 `source_sentence` 证据）：

| 论文 | 通道 A / B 记录数 | 合并后 |
|---|---|---|
| Sun 2022 (Acta Mater, 10.1016/j.actamat.2022.118282) | 85 / 50 | 107 |
| Starikov 2018 (JNM, 10.1016/j.jnucmat.2017.11.047) | 133 / 68 | 188 |
| Kim/Hofman/Cheon 2013 (JNM, 10.1016/j.jnucmat.2013.01.291) | 102 / 182 | 237 |
| Hirschhorn 2020 (JNM, 10.1016/j.jnucmat.2019.151929) | 39 / 96 | 117 |
| Doyle 2025 (JNM, 10.1016/j.jnucmat.2025.155851) | 229 / 152 | 278 |

- **合并与自审计**：`etl.fulltext_pilot merge`（值一致 > 名称 token Jaccard≥0.5）+ 机械化自审计（数值是否出现在出处句中，容忍 OCR 冒号小数 / 丢失 × 号的科学计数）；OCR 损坏指数（如 `1  10⁻⁹` 印作 `1  109`）诚实记 `no`。
- **ETL 验收**：927/927 **100% 通过**，0 fatal（[batch2-pilot-acceptance.json](batch2-pilot-acceptance.json)）。confidence：high 143 / medium 559 / low 225——独立会话下双通道命中率低于批次 1 的同会话两遍（批次 1 high 占 83%），印证批次 1 的一致性确被高估。
- **金标对照**（仅 kim_2013 有 corpus-snapshot 金标，33 条）：宽松口径 P=0.11 / **R=0.82**（27/33），严格口径 P=0.06 / R=0.45。低 precision 主因是本次穷举式抽取（237 条 vs 金标精选 33 条）+ 单位串异构（同批次 1 结论 2）。
- **产物**：[batch2-records/](batch2-records/)（927 条带证据记录）；复现：`data/fulltext-pilot/audit_batch2.py`（自审计）→ `export_batch2.py`（id + 受控 category 映射）→ `uv run python -m etl.acceptance --source-dir data/fulltext-pilot/channels/records` → `uv run python -m etl.fulltext_pilot evaluate ...`。
- **修复**：`etl.fulltext_pilot` CLI 子命令注册 bug（`add_argument`→`add_parser`）、金标 `value` 字段回退、单位 NFKD 折叠（`cm⁻³`→`cm-3`）；13 个单测全绿。

### 批次 2 结论

1. 独立会话双通道协议可行且全程机械化（抽取→合并→自审计→confidence→ETL 验收），可直接复用为后续全文抽取的标准作业流程。
2. confidence 分布对「会话独立性」敏感：独立会话 high 占比 15%（批次 1 同会话 83%），ChatExtract 判据在独立会话下更保守、更可信。
3. 单位受控词表仍是最大管线瓶颈（两批次一致）；recall 高、precision 受金标覆盖面与单位异构压制。
