# 单一 NFMD_DB_URL，无机密默认值

2026-09 配置 seam 战役决定：ETL 与 API 共用单一 `NFMD_DB_URL` 环境变量，默认值为本地 Docker PostgreSQL URL（`postgres:postgres` 是 Docker 镜像标准口令，非机密，与 `.env.example` 一致）。历史上两套互相矛盾的 fallback（ETL 指向 54322 Supabase 式 URL，API 指向 5432/nfmd 且内嵌角色口令）废除；`nfmd_read_2026` / `nfmd_write_2026` 等角色口令从源码删除，只经环境/部署侧提供。其余配置（source 目录、runs 目录、批量大小）收编进 `Settings.from_env`，同样不在 import 时读取。

## Considered Options

- **fail-fast，无任何默认**：缺 `NFMD_DB_URL` 即启动失败——否决，本地开发 DX 损失大于收益；连接失败时自然报错即可。
- **每组件独立环境变量（API 与 ETL 各一套）**：否决，这正是两套 fallback 漂移分叉的根源。
