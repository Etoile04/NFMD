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
