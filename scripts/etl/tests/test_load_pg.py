"""Integration tests: load_records against real PostgreSQL.

会话级一次性数据库（见 conftest.test_db_url），无库自动 skip。
钉住两个历史 bug 的正确行为：
1. ON CONFLICT UPDATE 被误计为 inserted（旧实现依赖 rowcount）；
2. 致命失败被折进 stats 字符串后正常返回（现在必须 raise）。
"""

import psycopg
import pytest
from load import LoadFatalError, load_records
from models import LoadStats

from etl.tests.test_load import _make_transformed_record

pytestmark = pytest.mark.integration


class TestInsertUpdateCounting:
    """inserted/updated 计数由预检查分支决定，不依赖 rowcount。"""

    def test_first_write_counted_as_inserted(self, materials_db):
        rec = _make_transformed_record(id="pg-ins-001", material_name="UO2")

        with psycopg.connect(materials_db) as conn:
            stats = load_records([rec], conn)

        assert stats.parameters_inserted == 1
        assert stats.parameters_updated == 0
        assert stats.parameters_errored == 0

    def test_same_id_new_scalar_counted_as_update(self, materials_db):
        """回归：同 id、business key 变化的 replace-run 重跑必须计 update。

        旧实现 INSERT ... ON CONFLICT DO UPDATE 后以 rowcount>0 计 inserted，
        对 UPDATE 同样成立，导致 inserted 虚增。
        """
        base = {"id": "pg-upd-001", "material_name": "UO2"}
        with psycopg.connect(materials_db) as conn:
            first = load_records(
                [_make_transformed_record(**base, value_scalar=10.0)], conn, mode="replace-run"
            )
            second = load_records(
                [_make_transformed_record(**base, value_scalar=12.0)], conn, mode="replace-run"
            )

        assert first.parameters_inserted == 1
        assert second.parameters_inserted == 0
        assert second.parameters_updated == 1

    def test_append_safe_rerun_writes_nothing(self, materials_db):
        rec = _make_transformed_record(id="pg-idem-001", material_name="UO2", value_scalar=21.5)

        with psycopg.connect(materials_db) as conn:
            first = load_records([rec], conn, mode="append-safe")
            second = load_records([rec], conn, mode="append-safe")

        assert first.parameters_inserted == 1
        assert second.parameters_inserted == 0
        assert second.parameters_skipped == 1

    def test_business_key_dedup_skips_across_ids(self, materials_db):
        """business key 相同、id 不同的记录：append-safe 第二条跳过。"""
        with psycopg.connect(materials_db) as conn:
            first = load_records(
                [_make_transformed_record(id="pg-dedup-a", material_name="UO2", value_scalar=7.0)],
                conn,
                mode="append-safe",
            )
            second = load_records(
                [_make_transformed_record(id="pg-dedup-b", material_name="UO2", value_scalar=7.0)],
                conn,
                mode="append-safe",
            )

        assert first.parameters_inserted == 1
        assert second.parameters_inserted == 0
        assert second.parameters_skipped == 1


class TestFatalPath:
    def test_missing_schema_raises_fatal(self, broken_db_url):
        """回归：致命失败必须 raise（旧实现折进 stats["errors"] 正常返回）。"""
        rec = _make_transformed_record()

        with (
            psycopg.connect(broken_db_url) as conn,
            pytest.raises(LoadFatalError),
        ):
            load_records([rec], conn)

    def test_fatal_error_carries_partial_stats(self, broken_db_url):
        rec = _make_transformed_record()

        with psycopg.connect(broken_db_url) as conn:
            try:
                load_records([rec], conn)
            except LoadFatalError as e:
                assert isinstance(e.stats, LoadStats)
            else:
                pytest.fail("expected LoadFatalError")
