#!/usr/bin/env bash
# NFMD API Server 启动脚本
# Usage: ./scripts/start_api.sh [--dev|--prod]
set -euo pipefail

cd "$(dirname "$0")"
HOST="0.0.0.0"
PORT=8900

# uv 管理的项目环境优先；否则回退到系统 python3
if command -v uv >/dev/null 2>&1; then
    PYTHON=(uv run python3)
else
    PYTHON=(python3)
fi

case "${1:-dev}" in
    --prod)
        echo "Starting NFMD API (production) on ${HOST}:${PORT}..."
        exec "${PYTHON[@]}" -m uvicorn api:app --host "$HOST" --port "$PORT" --workers 2
        ;;
    --dev|*)
        echo "Starting NFMD API (dev) on ${HOST}:${PORT}..."
        echo "Swagger docs: http://localhost:${PORT}/docs"
        exec "${PYTHON[@]}" -m uvicorn api:app --host "$HOST" --port "$PORT" --reload
        ;;
esac
