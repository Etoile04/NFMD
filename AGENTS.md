# AGENTS.md — NFMD (Nuclear Fuel Material Database)

核燃料材料参数知识库：ETL 管线（`scripts/etl/`）+ FastAPI 只读 API（`scripts/api.py`）+ PostgreSQL 16（RLS、触发器、tsvector 全文检索）。架构与 API 参考见 [README.md](README.md)。

**数据库操作安全红线**：任何 DB 写操作前先读 [docs/database-safety-rules.md](docs/database-safety-rules.md)（🔴 禁止无 WHERE 的 DELETE/UPDATE、DROP、TRUNCATE；🟡 影响 >100 行或 schema 变更需人工批准）。

**历史布局**：`docs/superpowers/`（plans、specs）是先前技能族留下的已完成整改记录，作为只读背景保留，与 `docs/agents/`、`docs/adr/` 布局共存，不要在其中新增文件。

## Agent skills

### Issue tracker

GitHub Issues（仓库 `Etoile04/NFMD`，经 `gh` CLI 读写）。See `docs/agents/issue-tracker.md`.

### Triage labels

五个规范 triage 角色均使用默认标签名。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context：根目录 `CONTEXT.md` + `docs/adr/`（按需懒创建；存在则先读）。See `docs/agents/domain.md`.
