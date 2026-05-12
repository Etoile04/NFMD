#!/usr/bin/env bash
# NFMD API Server 启动脚本
# Usage: ./scripts/start_api.sh [--dev|--prod]
set -e

PYTHON="/home/z203/.hermes/hermes-agent/venv/bin/python3"
HOST="0.0.0.0"
PORT=8900

case "${1:-dev}" in
    --prod)
        echo "Starting NFMD API (production) on ${HOST}:${PORT}..."
        exec $PYTHON -m uvicorn scripts.api:app --host "$HOST" --port "$PORT" --workers 2
        ;;
    --dev|*)
        echo "Starting NFMD API (dev) on ${HOST}:${PORT}..."
        echo "Swagger docs: http://localhost:${PORT}/docs"
        exec $PYTHON -m uvicorn scripts.api:app --host "$HOST" --port "$PORT" --reload
        ;;
esac
