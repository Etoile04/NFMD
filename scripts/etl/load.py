"""Load: Batch write transformed records to PostgreSQL.

ADR-0002：连接由调用方注入并负责关闭（组合根=run_pipeline）；
批内单条失败被隔离计数，致命失败 raise LoadFatalError（不再折进
stats 字符串后正常返回）。SQL 一律单行字面量 + %s 占位符，与
execute 同行——参数化形态可被安全门禁机检；写路径沿用本模块
既有的 SELECT-then-write 预检查风格（单写者 ETL，无并发竞态），
inserted/updated 计数由预检查分支决定，不依赖 rowcount。
"""

import psycopg
from psycopg.types.json import Jsonb

from etl.logging_config import get_logger
from etl.models import LoadStats, TransformedRecord

logger = get_logger(__name__)


class LoadFatalError(RuntimeError):
    """致命失败——整跑无法继续；携带已完成部分的部分 LoadStats。"""

    def __init__(self, message: str, stats: LoadStats):
        super().__init__(message)
        self.stats = stats


def normalize_source_file(source_file: str | None) -> str | None:
    """Normalize source_file to literature.id format.

    Handles patterns found in the wild:
    - summaries/xxx.md → xxx
    - summaries/xxx.txt.md → xxx
    - raw/mineru/xxx/paper.md → xxx
    - raw/papers/xxx → xxx
    - xxx.md → xxx
    - xxx.json → xxx
    - bare id → id (unchanged)
    """
    if not source_file:
        return source_file
    s = source_file
    if s.startswith("summaries/"):
        s = s.removeprefix("summaries/")
        s = s.removesuffix(".txt.md").removesuffix(".md")
    elif s.startswith("raw/mineru/"):
        s = s.removeprefix("raw/mineru/").split("/")[0]
    elif s.startswith("raw/papers/"):
        s = s.removeprefix("raw/papers/")
    else:
        s = s.removesuffix(".md").removesuffix(".json")
    return s


def load_records(
    records: list[TransformedRecord],
    conn: psycopg.Connection,
    mode: str = "append-safe",
    *,
    batch_size: int = 500,
) -> LoadStats:
    """
    Load transformed records into the database.

    Modes: append-safe (skip existing), replace-run (upsert).
    conn 由调用方提供并关闭；批间提交、批内隔离；致命失败 raise。
    """
    stats = LoadStats()
    try:
        # Step 1: Build material lookup (name -> id)
        material_lookup = _build_material_lookup(conn)
        logger.info("Material lookup: %d canonical names", len(material_lookup))

        # Step 2: Group records by literature_id and upsert literature
        lit_groups = {}
        for rec in records:
            if rec.literature_id and rec.literature_id not in lit_groups:
                lit_groups[rec.literature_id] = rec
        logger.info("Literature entries: %d", len(lit_groups))
        _upsert_literature(conn, list(lit_groups.values()), mode, stats)

        # Step 3: Load parameters in per-batch transactions
        total = len(records)
        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            try:
                _load_parameter_batch(conn, batch, material_lookup, mode, stats)
                conn.commit()
            except Exception as e:  # noqa: BLE001 — isolate batch failure, pipeline continues
                conn.rollback()
                stats.parameters_errored += len(batch)
                stats.errors.append(f"batch@{i}: {str(e)[:200]}")

            done = min(i + batch_size, total)
            logger.info("Progress: %d/%d parameters", done, total)

        logger.info("All batches processed")

    except Exception as e:
        conn.rollback()
        logger.error("Load error: %s", e)
        raise LoadFatalError(str(e), stats) from e

    return stats


def _build_material_lookup(conn: psycopg.Connection) -> dict[str, str]:
    """Build canonical_name -> uuid lookup from materials table."""
    lookup = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM materials")
        for row in cur.fetchall():
            lookup[row[1]] = str(row[0])
    return lookup


def _upsert_literature(
    conn: psycopg.Connection,
    records: list[TransformedRecord],
    mode: str,
    stats: LoadStats,
) -> None:
    """Upsert literature entries, mutating stats."""
    with conn.cursor() as cur:
        for rec in records:
            try:
                if mode == "append-safe":
                    # Check if exists
                    cur.execute("SELECT 1 FROM literature WHERE id = %s", (rec.literature_id,))
                    if cur.fetchone():
                        continue

                cur.execute("INSERT INTO literature (id, title, year, parameter_count) VALUES (%s, %s, %s, 0) ON CONFLICT (id) DO UPDATE SET title = COALESCE(EXCLUDED.title, literature.title), year = COALESCE(EXCLUDED.year, literature.year)", (rec.literature_id, rec.source_file, rec.literature_year))
                stats.literature_upserted += 1
            except Exception as e:  # noqa: BLE001 — isolate record failure
                stats.literature_errors += 1
                if stats.literature_errors <= 3:
                    logger.error("Literature error %s: %s", rec.literature_id, e)


def _load_parameter_batch(
    conn: psycopg.Connection,
    batch: list[TransformedRecord],
    material_lookup: dict[str, str],
    mode: str,
    stats: LoadStats,
) -> None:
    """Load a batch of parameters with business-key dedup, mutating stats."""
    with conn.cursor() as cur:
        for rec in batch:
            try:
                # Resolve material_id
                material_id = None
                if rec.material_name and rec.material_name in material_lookup:
                    material_id = material_lookup[rec.material_name]
                    stats.material_resolved += 1
                elif rec.material_name:
                    stats.material_unresolved += 1

                # Handle value_list serialization — must use Jsonb wrapper
                # so psycopg can infer the PostgreSQL type even when value is None
                value_list = Jsonb(rec.value_list) if rec.value_list is not None else Jsonb(None)

                # Normalize source_file to literature.id format
                normalized_source = normalize_source_file(rec.source_file)

                # Business-key dedup: check if (name, material_id, category, value_type, value_scalar, unit) already exists
                # This prevents duplicate records with different ids but same content
                if mode in ("append-safe", "replace-run"):
                    cur.execute("SELECT id FROM parameters WHERE name = %s AND category = %s AND value_type = %s AND (material_id = %s::uuid OR (material_id IS NULL AND %s::uuid IS NULL)) AND (value_scalar = %s::numeric OR (value_scalar IS NULL AND %s::numeric IS NULL)) AND (unit = %s::text OR (unit IS NULL AND %s::text IS NULL)) LIMIT 1", (rec.name, rec.category, rec.value_type, material_id, material_id, rec.value_scalar, rec.value_scalar, rec.unit, rec.unit))
                    existing = cur.fetchone()
                    existing_id = existing[0] if existing else None
                    if existing_id is None and mode == "replace-run":
                        # same id, different business key → update in place
                        cur.execute("SELECT 1 FROM parameters WHERE id = %s", (rec.id,))
                        if cur.fetchone():
                            existing_id = rec.id
                    if existing_id is not None:
                        if mode == "append-safe":
                            stats.parameters_skipped += 1
                            continue
                        # 一条逻辑 UPDATE 拆两条执行（安全门禁的字面量长度上限），同一事务内等价
                        cur.execute("UPDATE parameters SET name_en=COALESCE(%s,name_en), symbol=COALESCE(%s,symbol), value_min=COALESCE(%s,value_min), value_max=COALESCE(%s,value_max), value_expr=COALESCE(%s,value_expr), value_list=COALESCE(%s,value_list), value_text=COALESCE(%s,value_text), value_str=COALESCE(%s,value_str), uncertainty=COALESCE(%s,uncertainty) WHERE id=%s", (rec.name_en, rec.symbol, rec.value_min, rec.value_max, rec.value_expr, value_list, rec.value_text, rec.value_str, rec.uncertainty, existing_id))
                        cur.execute("UPDATE parameters SET temperature_k=COALESCE(%s,temperature_k), temperature_str=COALESCE(%s,temperature_str), burnup_range=COALESCE(%s,burnup_range), method=COALESCE(%s,method), confidence=COALESCE(%s,confidence), source_file=COALESCE(%s,source_file), equation=COALESCE(%s,equation), notes=COALESCE(%s,notes) WHERE id=%s", (rec.temperature_k, rec.temperature_str, rec.burnup_range, rec.method, rec.confidence, normalized_source, rec.equation, rec.notes, existing_id))
                        stats.parameters_updated += 1
                        continue

                if mode == "append-safe":
                    # Check if same id exists
                    cur.execute("SELECT 1 FROM parameters WHERE id = %s", (rec.id,))
                    if cur.fetchone():
                        stats.parameters_skipped += 1
                        continue

                cur.execute("INSERT INTO parameters (id, name, name_en, name_zh, symbol, category, subcategory, value_type, value_scalar, value_min, value_max, value_expr, value_list, value_text, value_str, unit, uncertainty, material_id, material_raw, temperature_k, temperature_str, burnup_range, method, confidence, source_file, equation, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (rec.id, rec.name, rec.name_en, rec.name_zh, rec.symbol, rec.category, rec.subcategory, rec.value_type, rec.value_scalar, rec.value_min, rec.value_max, rec.value_expr, value_list, rec.value_text, rec.value_str, rec.unit, rec.uncertainty, material_id, rec.material_raw, rec.temperature_k, rec.temperature_str, rec.burnup_range, rec.method, rec.confidence, normalized_source, rec.equation, rec.notes))
                stats.parameters_inserted += 1

            except Exception as e:  # noqa: BLE001 — isolate record failure
                stats.parameters_errored += 1
                if stats.parameters_errored <= 5:
                    stats.errors.append(f"{rec.id}: {str(e)[:200]}")
