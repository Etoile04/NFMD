"""Tests for io_utils module."""

import os

import pytest

from io_utils import write_jsonl, read_jsonl, stream_jsonl, write_json, read_json


# ===========================================================================
# TestJsonlIO
# ===========================================================================


class TestJsonlIO:
    """Tests for JSONL read/write operations."""

    def test_write_and_read_roundtrip(self, tmp_jsonl_file):
        """Write a list of dicts, read back identical."""
        data = [
            {"id": 1, "name": "alpha", "value": 3.14},
            {"id": 2, "name": "beta", "value": 2.72},
        ]
        write_jsonl(tmp_jsonl_file, data)
        result = read_jsonl(tmp_jsonl_file)
        assert result == data

    def test_stream_reads_one_at_a_time(self, tmp_jsonl_file):
        """stream_jsonl yields one dict per line."""
        data = [{"n": i} for i in range(5)]
        write_jsonl(tmp_jsonl_file, data)

        items = list(stream_jsonl(tmp_jsonl_file))
        assert len(items) == 5
        for i, item in enumerate(items):
            assert item == {"n": i}

    def test_empty_write_produces_empty_file(self, tmp_jsonl_file):
        """Writing [] produces a file that reads back as []."""
        write_jsonl(tmp_jsonl_file, [])
        assert read_jsonl(tmp_jsonl_file) == []

    def test_read_nonexistent_raises(self):
        """Reading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_jsonl("/tmp/nfmd_test_nonexistent_42.jsonl")


# ===========================================================================
# TestJsonIO
# ===========================================================================


class TestJsonIO:
    """Tests for JSON read/write operations."""

    def test_write_and_read_roundtrip(self, tmp_path):
        """JSON round-trip preserves data."""
        data = {"key": "value", "nested": {"a": 1, "b": [2, 3]}}
        path = str(tmp_path / "test.json")
        write_json(path, data)
        result = read_json(path)
        assert result == data

    def test_read_nonexistent_raises(self):
        """Reading a non-existent JSON file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_json("/tmp/nfmd_test_nonexistent_42.json")
