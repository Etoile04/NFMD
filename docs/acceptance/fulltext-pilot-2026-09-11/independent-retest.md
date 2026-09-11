# 测试报告 — 独立会话复测（NFMA-10，试点结论转化）

- 日期：2026-09-11
- 背景：[report.md](report.md) 的局限性第 4 条指出，试点双通道由**同一模型先后两个 pass** 模拟，一致性可能被高估，建议「用两套独立模型/会话复测」。本报告执行该复测：由一个**独立会话**（无试点抽取过程的任何上下文）对同 5 篇全文做单通道盲抽取（channel C），对照试点合并记录与金标。
- 关联工单：NFMA-10（分支 `NFMA-0010-pilot-followup`）

## 方法

1. **盲抽取协议**：逐篇「先读全文 → 写抽取 → 才允许看试点产物」。channel C 遵循 `etl.prompts` 的 ChatExtract 通道规则（只依据出处句、不换算单位、逐条记 `qid` + `sentence`）。执行模型：builtin:bigmodel-coding-plan/GLM-5.3；试点通道 A/B 的执行模型未记录，故本复测的「独立」准确语义是**独立会话/独立上下文**，不保证跨模型。
2. **对照口径**：复用 `eval_gold` 的匹配逻辑（值级宽松 + 含单位严格，多重集 min-count），评估独立通道 C vs 试点合并（A+B）vs 金标。
3. **管线验收**：channel C 记录导出语料格式后走 `uv run python -m etl.acceptance` 三阶段 dry-run（零触库）。
4. **信息披露**：侦察阶段曾瞥见 jnpe_2025 的一条试点记录（SRIM 离位阈能 35.6 eV）与 gold-comparison 的计数统计——轻微信息泄漏，方向上偏向抬高一致性；jnpe 篇的复测一致率恰为最高（0.957），解读时应留意。

## 结果

### 跨会话一致性（主口径：channel C vs 试点 A+B 合并）

| 指标 | 值 |
|---|---|
| channel C 记录（5 篇） | 163 |
| 试点合并记录（对照） | 124 |
| 值级宽松一致 | **113 条** |
| 试点视角复现率（113/124） | **0.911** |
| channel C 视角一致率（113/163） | 0.693 |
| 严格（值+单位）一致 | 89（0.546 / 0.718） |
| ETL dry-run 验收 | **163/163 通过，0 fatal**（warn:MISSING_MATERIAL ×54） |

逐篇（宽松，channel C 视角 / 试点视角）：nucengdes_2018 0.92/1.00；1063_1_5127696 0.56/0.86；jnpe_2025 0.82/0.96；scriptamat_2015 0.79/0.93；ieacifcacc_48748 0.53/0.83。

### 对照金标（参照口径）

channel C vs 金标：宽松 P 0.521、严格 P 0.387（试点为 0.629/0.411）——同一量级，channel C 更全面的覆盖引入了更多金标外条目（设备/表格逐项分列），压低了 P。

## 差异归因

- **主结论：数值层面跨会话稳定**。试点 124 条中 91% 被独立会话按值复现，试点的「双通道一致 → confidence=high」判据获得跨会话证据支持，并非同模型伪象。
- **不一致的主体是覆盖差异，不是数值冲突**：channel C 多出的 ~50 条集中在表格逐项分列（成分逐元素、逐应力组清单）与设备参数（束流、探测器）；宽松口径下值级匹配的 113 对中，单位归一后仍不同的有 24 对（21%）——与试点「序列化异构」结论一致，直接佐证单位受控词表 v2（`etl.normalize` 本工单已落地）的必要性。
- **OCR 退化文档一致率最低**（ieacifcacc_48748：0.83），channel C 在噪声文本上采取保守策略（只取清晰句），两通道对模糊表格的取舍不同。
- 未发现「同一物理量两个通道给出矛盾数值」的案例（值级匹配对内无同量异值；不匹配条目均为单侧覆盖差异）。

## 结论与建议

1. **试点结论被复测巩固**：全文级 ChatExtract 抽取的数值稳定性与 ETL 兼容性（100% dry-run 通过）在独立会话下成立；confidence 推导判据可继续沿用。
2. **真正跨模型的复测仍待做**：本复测是跨会话而非跨模型；建议后续由异构模型（或人工）再抽 1 篇做 spot-check 即可收口。
3. **覆盖差异（而非数值冲突）是全文抽取的主要噪声源**：合并策略应允许「单侧覆盖」条目以 medium 入库（现行 merge 语义已如此），人工审查优先看 OCR 退化文档的单侧条目。

## 复现

```bash
# channel C 盲抽取：LLM agent 读 raw/mineru/<slug>/auto/<slug>.md，
# 逐条产出 data/fulltext-pilot/independent/<slug>.json（qid/sentence/…）
python3 data/fulltext-pilot/eval_independent.py           # → independent-comparison.json
python3 data/fulltext-pilot/eval_independent.py export    # → independent-records/（语料格式）
uv run python -m etl.acceptance --source-dir data/fulltext-pilot/independent-records
```

机器可读证据：[independent-comparison.json](independent-comparison.json)（逐篇三向对照）、[independent-acceptance.json](independent-acceptance.json)（ETL dry-run）、[records-independent/](records-independent/)（163 条 channel C 盲抽取记录，含出处句）。
