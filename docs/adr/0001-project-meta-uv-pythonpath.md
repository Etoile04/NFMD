# 项目元信息采用 uv 管理 + pytest pythonpath，保留 scripts/etl 布局

2026-09 架构走查（PR #2 已合入）决定：依赖与工具链由 uv 管理（`uv.lock` + `.python-version` + `[dependency-groups]`），ruff 规则面 E/F/I/UP/B/SIM（`scripts/api.py` 忽略 B008）。测试导入改经 pyproject 的 `pythonpath = ["scripts/etl"]`，移除了测试源码内的 sys.path hack；`scripts/etl/run_pipeline.py` 保留自身 CLI 引导用的一处 insert。**不迁移真包**，`scripts/etl` 布局保留。CI 为 ruff check + pytest 两个 job，单版本 Python 3.14。

## Considered Options

- **真包 `nfmd_etl/` + setuptools + console 入口**：更彻底地消灭裸名导入与撞名，但与已合入的 uv 方案构成重复建设，否决；真包迁移保留为后续深化机会。
