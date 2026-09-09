#!/bin/bash
# NFMD ETL 启动脚本：uv run 优先（editable 安装保证 etl 包可导入，cwd 无关）
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
    exec uv run python -m etl.run_pipeline "$@"
else
    exec python3 -m etl.run_pipeline "$@"
fi
