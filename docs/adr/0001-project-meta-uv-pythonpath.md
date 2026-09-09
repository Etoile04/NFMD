# 项目元信息采用 uv 管理 + pytest pythonpath，保留 scripts/etl 布局

2026-09 深化候选 6 决定（PR #2 已合入）：依赖与工具链由 uv 管理（`uv.lock` + `.python-version` + `[dependency-groups]`），ruff 规则面 E/F/I/UP/B/SIM（`scripts/api.py` 忽略 B008），测试经 pyproject 的 `pythonpath = ["scripts/etl"]` 导入——移除了源码内 sys.path hack 但**不迁移真包**，`scripts/etl` 布局保留。CI 为 ruff check + pytest 两个 job，单版本 Python 3.14。

## Considered Options

- **真包 `nfmd_etl/` + setuptools + console 入口**（2026-09-09 另一轮 grilling 曾定此案）：更彻底地消灭裸名导入与撞名，但与已合入的 uv 方案构成重复建设，搁置；真包迁移仍是挂起的深化机会（架构报告候选 3），届时以增量 PR 在 uv 方案之上实施。
- **CI 3.10+3.14 矩阵 + postgres:16 service container + mypy + ruff format --check**：同一轮共识的其余项，尚未落地，列为后续工单（集成测试依赖 postgres 容器先行）。
