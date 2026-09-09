# 原地包化：scripts/etl 作为 `etl` 包 editable 安装

**状态：采纳（2026-09）**。部分取代 ADR-0001 中"真包迁移保留为后续深化机会、不与 uv 方案同时做"的否决结论。

架构评审候选 3 落地：`scripts/etl` 目录原封不动，经 `[build-system]`（hatchling）+ `[tool.hatch.build.targets.wheel] packages = ["scripts/etl"]` 声明为顶层包 `etl`，`uv sync` 自动以 editable 方式安装本项目。全部内部导入改绝对包路径（`from etl.config import ...`），包内模块 `load`/`models`/`rules`/`config` 的裸名撞车结构性消失。

随之消灭的路径 hack 共三处：`run_pipeline.py` 的 `sys.path.insert`、`run_etl.sh` 的 `PYTHONPATH=scripts/etl`、pyproject pytest 的 `pythonpath` 配置——导入解析全部收敛到 editable 安装这一条通道，任意 cwd 可 `python -m etl.run_pipeline` / `uvicorn etl.api:app`。

api.py 从 `scripts/api.py` 移入包内（`etl.api`）：这是"彻底删除 pythonpath"的必然推论——留在包外则测试 `import api` 无解析路径。启动脚本不再需要 cd scripts。

## Considered Options

- **src 布局迁移（`src/nfmd_etl/` + tests 移根目录）**：更"标准"但需移动 ~15 个文件并改 README/CI 引用，无增量收益，否决；原地包化零文件移动即达成全部目标（api.py 入包是唯一例外）。
- **相对导入（`from .config import`）**：与 api.py 既有的绝对导入不一致、grep 不友好，否决。
- **维持 pytest pythonpath**：等于留一条与 editable 安装并行的第二解析通道，违背"消灭 hack"的目标，否决。

## 与 ADR-0001 的关系

ADR-0001 否决的是当时"setuptools+真包**重做**候选 6"的提案（与刚合入的 uv 方案重复建设），并注明"真包迁移保留为后续深化机会"。本 ADR 兑现该保留项：包化作为独立候选单独成案，不推翻 ADR-0001 的 uv 工具链决策。
