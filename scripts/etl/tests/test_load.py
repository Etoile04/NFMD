"""Tests for load module (database layer).

Uses mocking (unittest.mock) to avoid requiring a live database connection.
"""

import os
import sys

import pytest

# Ensure scripts/etl/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from load import load_records, _build_material_lookup, _upsert_literature
from models import TransformedRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transformed_record(**overrides) -> TransformedRecord:
    """Build a minimal TransformedRecord with sensible defaults."""
    defaults = dict(
        id="param-001",
        name="density",
        name_en="density",
        category="physical_property",
        value_type="scalar",
        value_scalar=15.6,
        unit="g/cm³",
        material_name="U-10Mo",
        material_raw="U-10Mo",
        temperature_k=293.0,
        source_file="test_paper.json",
        literature_id="lit-001",
        literature_year=2024,
    )
    defaults.update(overrides)
    return TransformedRecord(**defaults)


# ===========================================================================
# TestBuildMaterialLookup
# ===========================================================================

class TestBuildMaterialLookup:
    """Tests for _build_material_lookup."""

    def test_returns_dict_mapping_names_to_ids(self):
        """Cursor returns material rows → dict maps name → id."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate SELECT id, name FROM materials
        mock_cursor.fetchall.return_value = [
            ("mat-001", "U-10Mo"),
            ("mat-002", "U-Zr"),
        ]

        result = _build_material_lookup(mock_conn)

        assert result == {"U-10Mo": "mat-001", "U-Zr": "mat-002"}
        mock_cursor.execute.assert_called_once_with("SELECT id, name FROM materials")

    def test_empty_database_returns_empty_dict(self):
        """No rows in materials table → empty dict."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchall.return_value = []

        result = _build_material_lookup(mock_conn)

        assert result == {}


# ===========================================================================
# TestUpsertLiterature
# ===========================================================================

class TestUpsertLiterature:
    """Tests for _upsert_literature."""

    def test_upserts_records(self):
        """Upserting a TransformedRecord with literature_id succeeds."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate: no existing row (append-safe SELECT returns nothing)
        mock_cursor.fetchone.return_value = None
        mock_cursor.rowcount = 1

        rec = _make_transformed_record()
        stats = _upsert_literature(mock_conn, [rec], mode="append-safe")

        assert stats["upserted"] == 1
        assert stats["errors"] == 0
        # Verify an INSERT was executed (at least 2 calls: SELECT check + INSERT)
        assert mock_cursor.execute.call_count >= 2

    def test_upsert_skips_existing_in_append_safe(self):
        """In append-safe mode, existing literature rows are skipped."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulate: row already exists
        mock_cursor.fetchone.return_value = ("1",)

        rec = _make_transformed_record()
        stats = _upsert_literature(mock_conn, [rec], mode="append-safe")

        assert stats["upserted"] == 0  # skipped
        assert stats["errors"] == 0


# ===========================================================================
# TestLoadRecordsErrorHandling
# ===========================================================================

class TestLoadRecordsErrorHandling:
    """Tests for load_records error handling."""

    def test_connection_failure_raises(self):
        """If get_connection raises, the exception propagates (called outside try)."""
        with patch("load.get_connection", side_effect=Exception("Connection refused")):
            records = [_make_transformed_record()]
            with pytest.raises(Exception, match="Connection refused"):
                load_records(records, db_url="postgres://bad-host/db")

    def test_empty_records_returns_zero_stats(self):
        """Loading an empty record list completes without errors."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        with patch("load.get_connection", return_value=mock_conn):
            stats = load_records([], db_url="postgres://test/db")

        assert stats["parameters_inserted"] == 0
        assert stats["parameters_errored"] == 0
        assert stats["errors"] == []
