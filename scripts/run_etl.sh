#!/bin/bash
cd "$(dirname "$0")/.."
PYTHONPATH=scripts/etl python3 scripts/etl/run_pipeline.py "$@"
