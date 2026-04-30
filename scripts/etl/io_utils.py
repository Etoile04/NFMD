"""JSONL I/O and run directory management."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Generator


def create_run_dir(base_dir: str = "data/imports/runs") -> tuple[str, str]:
    """Create a timestamped run directory. Returns (run_id, run_dir_path)."""
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = os.path.join(base_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_id, run_dir


def open_run_dir(run_id: str, base_dir: str = "data/imports/runs") -> str:
    """Open an existing run directory."""
    run_dir = os.path.join(base_dir, run_id)
    if not os.path.isdir(run_dir):
        raise FileNotFoundError(f"Run directory not found: {run_dir}")
    return run_dir


def write_jsonl(path: str, records: list[dict[str, Any]]) -> None:
    """Write records to a JSONL file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: str) -> list[dict[str, Any]]:
    """Read records from a JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def stream_jsonl(path: str) -> Generator[dict[str, Any], None, None]:
    """Stream records from a JSONL file (memory efficient)."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: str, data: Any) -> None:
    """Write data to a JSON file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def read_json(path: str) -> Any:
    """Read data from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
