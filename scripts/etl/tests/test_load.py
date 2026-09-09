"""Tests for load module contract (unit level, DB-free via fakes).

load_records 的 interface 契约（ADR-0002）：conn 由调用方注入且绝不
关闭；批内失败隔离计数；致命失败 raise LoadFatalError。真实 SQL 行为
见 test_load_pg.py（integration）。
"""

from unittest.mock import MagicMock

import psycopg
import pytest
from load import (
    LoadFatalError,
    _build_material_lookup,
    _upsert_literature,
    load_records,
)
from models import LoadStats, TransformedRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transformed_record(**overrides) -> TransformedRecord:
    """Build a minimal TransformedRecord with sensible defaults."""
    defaults = {
        "id": "param-001",
        "name": "density",
        "name_en": "density",
        "category": "physical_property",
        "value_type": "scalar",
        "value_scalar": 15.6,
        "unit": "g/cm³",
        "material_name": "U-10Mo",
        "material_raw": "U-10Mo",
        "temperature_k": 293.0,
        "source_file": "test_paper.json",
        "literature_id": "lit-001",
        "literature_year": 2024,
    }
    defaults.update(overrides)
    return TransformedRecord(**defaults)


def _fake_conn(cursor: MagicMock | None = None) -> MagicMock:
    """Connection fake：cursor() 返回给定游标 fake（或全新 MagicMock）。"""
    conn = MagicMock()
    cursor = cursor or MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


# ===========================================================================
# TestBuildMaterialLookup
# ===========================================================================

class TestBuildMaterialLookup:
    """Tests for _build_material_lookup."""

    def test_returns_dict_mapping_names_to_ids(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("mat-001", "U-10Mo"), ("mat-002", "U-Zr")]

        result = _build_material_lookup(_fake_conn(cursor))

        assert result == {"U-10Mo": "mat-001", "U-Zr": "mat-002"}

    def test_empty_database_returns_empty_dict(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []

        assert _build_material_lookup(_fake_conn(cursor)) == {}


# ===========================================================================
# TestUpsertLiterature
# ===========================================================================

class TestUpsertLiterature:
    """Tests for _upsert_literature (mutates a LoadStats)."""

    def test_upserts_new_literature(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # append-safe 预检查：不存在
        cursor.rowcount = 1

        stats = LoadStats()
        _upsert_literature(_fake_conn(cursor), [_make_transformed_record()], "append-safe", stats)

        assert stats.literature_upserted == 1
        assert stats.literature_errors == 0
        # 至少两步：SELECT 预检查 + INSERT
        assert cursor.execute.call_count >= 2

    def test_skips_existing_in_append_safe(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("1",)  # 已存在

        stats = LoadStats()
        _upsert_literature(_fake_conn(cursor), [_make_transformed_record()], "append-safe", stats)

        assert stats.literature_upserted == 0
        assert stats.literature_errors == 0


# ===========================================================================
# TestLoadRecordsContract
# ===========================================================================

class TestLoadRecordsContract:
    """load_records 的 seam 契约。"""

    def test_empty_records_returns_zero_stats(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []  # material lookup 为空

        stats = load_records([], _fake_conn(cursor))

        assert stats == LoadStats()

    def test_fatal_failure_raises_and_rolls_back(self):
        """致命失败：raise LoadFatalError 并回滚，而非折进 stats 正常返回。"""
        conn = _fake_conn()
        conn.cursor.return_value.__enter__.side_effect = psycopg.OperationalError("relation materials does not exist")

        with pytest.raises(LoadFatalError, match="relation materials"):
            load_records([_make_transformed_record()], conn)

        conn.rollback.assert_called_once()

    def test_never_closes_connection(self):
        """连接生命周期归调用方——load_records 绝不 close。"""
        conn = _fake_conn()

        load_records([], conn)

        conn.close.assert_not_called()

    def test_connection_opened_by_caller_not_module(self):
        """模块不再自建连接：不导入 get_connection 之类的内部工厂。"""
        import load

        assert not hasattr(load, "get_connection")
