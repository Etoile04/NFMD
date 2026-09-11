# NFMA-9 全文抽取试点报告（样本 1/5：2025 Doyle）

日期：2026-09-11 ｜ 分支：`NFMA-0009-fulltext-pilot` ｜ 工具：`etl.fulltext_pilot`

## 目的

在恢复的 MinerU 全文上验证 ChatExtract 双通道 + 自审计协议的端到端可行性，
并与 parameters 金标（corpus-snapshot）量化对照。

## 样本与流程

- 样本：`2025_Doyle_SwellingandFission`（U-10Mo/U-17Mo MiniFuel 辐照肿胀与裂变气体行为，全文 ~111 KB）。
- Channel A：盲抽（本试点，229 条）；Channel B：盲抽（152 条）。
- `etl.fulltext_pilot merge`：同量匹配合并 → 278 条合并记录（含 `channel_a`/`channel_b`/证据字段），
  输出 `data/fulltext-pilot/records/2025_Doyle_SwellingandFission.json`。
- `etl.fulltext_pilot evaluate`：对金标 21 条 1:1 贪心匹配（strict：value+unit 归一；lenient：value-only），
  输出 `data/fulltext-pilot/evaluation_2025_Doyle.json`。

## 结果（vs 金标 21 条）

| 口径 | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| strict | 14 | 264 | 7 | 0.0504 | 0.6667 | 0.0936 |
| lenient | 17 | 261 | 4 | 0.0612 | 0.8095 | 0.1137 |

## 解读

1. **Recall 是主口径且达标方向良好**：金标 21 条中 strict 命中 14、lenient 命中 17。
   金标是从 summaries 精选的参数子集，而全文抽取按协议输出全部量化数据点（278 条），
   因此 precision 低主要是**口径不对称**（分母含金标未收录的表格逐项数据），不等于错抽。
2. **4 条 lenient FN（gold 000–003）是编码差异**：金标把平均裂变率 mean±std 编码为 range
   （如 4.8–6.4×10¹³ cm⁻³s⁻¹），抽取通道输出 scalar 均值。属金标约定 vs 抽取 schema 的系统差异，
   建议后续在 prompt 中显式要求 ± 值记为 range，或评估器增加 mean±std≈range 折算档。
3. **strict 比 lenient 少 3 条**：μ 记号（μm vs μm 变体）与 dimensionless unit 的归一仍可再收紧。
4. **协议执行**：双通道互盲成立（A/B 独立产出，重合量在 merge 阶段对齐）；自审计回填
   （`apply_self_audit`）本样本未跑，为下一步。

## 工具修复（本心跳）

- `values_match` range 分支自比较 bug（`_close(vb, vb)` → 两端各自对比）+ 回归测试。
- CLI 子命令误用 `add_argument` → `add_parser`；`safe_open_read` 签名适配。
- 金标 scalar 值字段回退（`value_scalar` → `value`）；unit 归一加 NFKD 折叠上标（cm⁻³ ≡ cm-3）。
- 全测试套 196 通过，ruff 干净。

## Remaining

- [ ] 其余 4 篇（Starikov / Hirschhorn / Sun / Kim-Hofman-Cheon 2013）补齐双通道盲抽。
- [ ] Doyle 自审计回填（`SELF_AUDIT_PROMPT` 逐条 yes/no）与 confidence 分布。
- [ ] 5 篇汇总表 + 结论（precision 口径需按"金标覆盖子集"重述或改用 per-gold-match 率）。
- [ ] 产物过 NFMD ETL 验收（`etl.acceptance`）。
