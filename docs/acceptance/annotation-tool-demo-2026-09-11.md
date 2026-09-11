# 标注工具全链路演示 — 2026-09-11

分支 `feature/annotation-tool`（annotation tooling — no ticket，看板被 RE 阻塞）。
工具：`uv run python -m etl.annotate serve`（默认 127.0.0.1:8910，源目录
`NFMD_ANNO_SOURCE_DIR`，输出 `NFMD_ANNO_OUT_DIR`）。规范：
`docs/annotation/guideline.md`。

## 演示论文

`2025_Doyle_SwellingandFission`（试点语料全文
`data/fulltext-pilot/fulltexts/`）。

## 全链路（HTTP 请求样例）

1. **取全文** `GET /api/fulltext/2025_Doyle_SwellingandFission` → 全文文本
   （左侧栏渲染，划选自动填 `source_sentence`，超 2 句自动截断）。
2. **标注人 ann1 标 3 条 → 保存** `POST /api/records/ann1/2025_Doyle_SwellingandFission`：

   ```json
   {"records": [
     {"name_en": "displacement threshold energy of U in SRIM calculation",
      "value_type": "scalar", "value_scalar": 35.6, "unit": "eV",
      "material": "U", "category": "simulation_parameter",
      "source_sentence": "…", "source_location": "Sec. 2", "notes": "SRIM input"},
     {"name_en": "porosity of U-10Mo fuel", "value_type": "range",
      "value_min": 4.0, "value_max": 6.0, "unit": "%",
      "material": "U-10Mo", "category": "microstructure", …},
     {"name_en": "swelling strain of U-10Mo", "value_type": "scalar",
      "value_scalar": 21.0, "uncertainty": "0.3", "unit": "%", …}]}
   ```

   保存即跑 `etl.validate` 规则引擎；非法记录（如 `name_en="parameter"` 触发
   `GENERIC_NAME`）返回 422 + issue 明细，不落盘。`uncertainty` 独立字段，
   不折叠进 range（ADR-0006 口径）。
3. **标注人 ann2 同标 3 条**（其中两条值有意偏离：range 4.1–6.1、scalar 21.5）。
4. **配对统计** `GET /api/arbitrate/<slug>?a=ann1&b=ann2` →
   `{total: 3, matched: 1, match_rate: 0.3333}`（仅值级一致计入 matched，
   分歧配对留给仲裁）。
5. **仲裁导出** `POST /api/arbitrate/<slug>`（decisions 全取 a 侧）→
   `gold/<slug>.json`，3 条，id 形如 `<slug>_gold_000`。
6. **D3 分桶评估**：构造一份带 1 处单位错的“抽取结果”（range 单位 `%` →
   `vol%`）与 gold 对照：

   ```
   buckets: matched=1, missed=1, unit_wrong=1, value_wrong=0, condition_wrong=0
   pilot lenient: P=1.0, R=0.6667, F1=0.8
   ```

   分桶由 `etl.annotate.bucketed_report` 产出，P/R/F1 复用
   `fulltext_pilot.evaluate_against_gold` 试点口径，未另起炉灶。

## 测试

`scripts/etl/tests/test_annotate.py` 24 项（四个预定接缝 + HTTP 层）；
全仓 `uv run pytest -q` 233 passed；`uv run ruff check .` clean。
