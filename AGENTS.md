# AGENTS.md — NFMD (Nuclear Fuel Material Database)

核燃料材料参数知识库：ETL 管线 + FastAPI 只读 API（同在 `etl` 包内：`scripts/etl/`，editable 安装，入口 `etl.run_pipeline` / `etl.api`）+ PostgreSQL 16（RLS、触发器、tsvector 全文检索）。架构与 API 参考见 [README.md](README.md)。

**数据库操作安全红线**：任何 DB 写操作前先读 [docs/database-safety-rules.md](docs/database-safety-rules.md)（🔴 禁止无 WHERE 的 DELETE/UPDATE、DROP、TRUNCATE；🟡 影响 >100 行或 schema 变更需人工批准）。

**历史布局**：`docs/superpowers/`（plans、specs）是先前技能族留下的已完成整改记录，作为只读背景保留，与 `docs/agents/`、`docs/adr/` 布局共存，不要在其中新增文件。

## Agent skills

### Issue tracker

GitHub Issues（仓库 `Etoile04/NFMD`，经 `gh` CLI 读写）。See `docs/agents/issue-tracker.md`.

### Triage labels

五个规范 triage 角色均使用默认标签名。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context：根目录 `CONTEXT.md` + `docs/adr/`（按需懒创建；存在则先读）。See `docs/agents/domain.md`.

## Agent operations (NFMZ)

本仓库的开发由 Paperclip 看板上的 NFMZ agent 公司承担：工单编号 `NFMA-###`，分支命名 `NFMA-XXXX-<slug>`；本仓库为独立版本线，不受其他仓库规则约束，提交信息按惯例引用 `NFMA-###`（无强制 gate）。

**当前交付物**：ETL 管线（`etl.run_pipeline` / `etl.api`）+ FastAPI 只读 API + PostgreSQL 16 schema（RLS）。Web 前端尚未启动——启动后 E2E 验收加入浏览器测试相（断点 1440 / 768 / 375，WCAG AA 基线）。

**版本线**：独立版本，`vX.Y.Z`（当前 0.x 阶段）；发布 = main 打 tag + GitHub Release（notes 引用对应 `NFMA-###` 工单）。

### 当前交付线

本仓（`Etoile04/NFMD`）是 NFMZ 看板的**独立 0.x 版本线**，独立打 tag（现至 `v0.4.0`）。上面「当前交付物」「版本线」两段描述的是 NFMD 自身，仍然成立。

**但 NFMZ 看板自 [NFMA-12](/NFMA/issues/NFMA-12)（接管 nfmd-check v2 改造）起的活跃交付线在 [`Etoile04/nfmd-check`](https://github.com/Etoile04/nfmd-check)**（另一条独立版本线，现至 `v1.0.0`）：那以后的 NFMZ 交付 PR 全部落在 nfmd-check 侧（该仓 PR 至 #126），NFMD 侧的交付 PR 止于 #17（NFMA-10）。**做标注 / 金标 / 评测 / serve 这一类工具链的工作，请到 nfmd-check 开工**，不要在 NFMD 侧新建同名文件——本仓已因此出现过「在 NFMD 里找不到那个文件」的误判。

**指针表**（路径与用途按 nfmd-check `origin/main` 实测写入，非凭记忆；命中数 = `git ls-tree -r --name-only origin/main -- <path>` 的输出行数）：

| nfmd-check 仓内路径 | 用途 | NFMD 侧命中 | nfmd-check 侧命中 |
|---|---|---|---|
| `docs/annotation/gold-expansion-manual.md` | 金标扩充手册（单人模式，NFMA-32）：冻结抽样方案 v1（2026-09-17 批准，主三类 + 备选四类配额、总量 ≈ 76–84 条 / 6 篇）、**v2 换篇更正（2026-10-02，Doyle 2025 改锚 `10_1016_j_jnucmat_2025_155851`）**、六篇文献的库内 slug 对照表、单人金标落地口径（`annotator=user` 首轮 / `annotator=user_qa` QA 复核，仲裁 `a=user,b=user_qa`）、§5 评测报告模板 | 0 | 1 |
| `scripts/serve-local.sh` | 标注器本地起栈脚本：优先复用 `.supabase-compose` 直连栈（rest / storage 端口取自 `.supabase-compose/.env`，缺省 18001 / 18002），未运行时回退 supabase CLI 栈（54331）。末行 `exec uv run nfmd-annotate serve "$@"`，故用法 `scripts/serve-local.sh --port 8910` | 0 | 1 |
| `scripts/eval_m2_grayscale.py` | M2 自动链金标灰度评测出分脚本（NFMA-21 收官步）：复用 `annotate.records.bucketed_report` 的分桶 strict/lenient P/R/F1，叠加 M2 自动链视角——baseline（原始 LLM 抽取 vs 金标）/ auto chain canonical（`derive_confidence` → `stamp_provenance`，阈值 0.90 / 0.70）/ 按参数类分桶 / export 白名单效果（`export_filter(gold+accepted)`）/ 10% 抽样复核清单。纯只读，不触 DB，结果落 JSON + stdout | 0 | 1 |

**同名陷阱**：`docs/annotation/guideline.md` 在**两个仓都有同名文件，但内容不同**（NFMD 侧 4203 字节、nfmd-check 侧 11991 字节，2026-10-24 实测）——NFMD 侧那份绑定本仓轻量标注器 `uv run python -m etl.annotate`（`scripts/etl/annotate.py`）；nfmd-check 侧那份绑定 `uv run nfmd-annotate serve`（`src/nfmd_check/annotate/` 包，pyproject 入口 `nfmd-annotate = nfmd_check.annotate:main`）。做金标扩充 / 评测要读的是 **nfmd-check 那份**，别把 NFMD 这份当成同一文件。
