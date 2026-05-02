"""Load: Batch write transformed records to Supabase PostgreSQL."""

import json
from typing import Optional

import psycopg
import psycopg.sql

from config import DB_URL, BATCH_SIZE

from logging_config import get_logger
from models import TransformedRecord

logger = get_logger(__name__)


def get_connection(db_url: str = DB_URL) -> psycopg.Connection:
    """Get a database connection."""
    return psycopg.connect(db_url, autocommit=False)


def load_records(
    records: list[TransformedRecord],
    db_url: str = DB_URL,
    mode: str = "append-safe",
) -> dict:
    """
    Load transformed records into the database.
    Modes: append-safe (skip existing), replace-run (upsert).
    Returns load summary stats.
    """
    stats = {
        "parameters_inserted": 0,
        "parameters_updated": 0,
        "parameters_skipped": 0,
        "parameters_errored": 0,
        "literature_upserted": 0,
        "literature_errors": 0,
        "material_resolved": 0,
        "material_unresolved": 0,
        "errors": [],
    }

    conn = get_connection(db_url)
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

        lit_stats = _upsert_literature(conn, list(lit_groups.values()), mode)
        stats["literature_upserted"] = lit_stats["upserted"]
        stats["literature_errors"] = lit_stats["errors"]

        # Step 3: Load parameters in per-batch transactions
        total = len(records)
        for i in range(0, total, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            try:
                batch_stats = _load_parameter_batch(conn, batch, material_lookup, mode)
                conn.commit()
            except Exception as e:
                conn.rollback()
                batch_stats = {"inserted": 0, "updated": 0, "skipped": 0, "errored": len(batch),
                               "material_resolved": 0, "material_unresolved": 0, "errors": [str(e)[:200]]}
            stats["parameters_inserted"] += batch_stats["inserted"]
            stats["parameters_updated"] += batch_stats["updated"]
            stats["parameters_skipped"] += batch_stats["skipped"]
            stats["parameters_errored"] += batch_stats["errored"]
            stats["material_resolved"] += batch_stats["material_resolved"]
            stats["material_unresolved"] += batch_stats["material_unresolved"]
            if batch_stats["errors"]:
                stats["errors"].extend(batch_stats["errors"][:5])

            done = min(i + BATCH_SIZE, total)
            logger.info("Progress: %d/%d parameters", done, total)

        logger.info("All batches processed")

    except Exception as e:
        conn.rollback()
        stats["errors"].append(f"FATAL: {str(e)}")
        logger.error("Load error: %s", e)
    finally:
        conn.close()

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
    conn: psycopg.Connection, records: list[TransformedRecord], mode: str
) -> dict:
    """Upsert literature entries."""
    stats = {"upserted": 0, "errors": 0}
    with conn.cursor() as cur:
        for rec in records:
            try:
                if mode == "append-safe":
                    # Check if exists
                    cur.execute("SELECT 1 FROM literature WHERE id = %s", (rec.literature_id,))
                    if cur.fetchone():
                        continue

                cur.execute(
                    """
                    INSERT INTO literature (id, title, year, parameter_count)
                    VALUES (%s, %s, %s, 0)
                    ON CONFLICT (id) DO UPDATE SET
                        title = COALESCE(EXCLUDED.title, literature.title),
                        year = COALESCE(EXCLUDED.year, literature.year)
                    """,
                    (rec.literature_id, rec.source_file, rec.literature_year),
                )
                stats["upserted"] += 1
            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] <= 3:
                    logger.error("Literature error %s: %s", rec.literature_id, e)
    return stats


def _load_parameter_batch(
    conn: psycopg.Connection,
    batch: list[TransformedRecord],
    material_lookup: dict[str, str],
    mode: str,
) -> dict:
    """Load a batch of parameters."""
    stats = {
        "inserted": 0, "updated": 0, "skipped": 0, "errored": 0,
        "material_resolved": 0, "material_unresolved": 0,
        "errors": [],
    }

    with conn.cursor() as cur:
        for rec in batch:
            try:
                # Resolve material_id
                material_id = None
                if rec.material_name and rec.material_name in material_lookup:
                    material_id = material_lookup[rec.material_name]
                    stats["material_resolved"] += 1
                elif rec.material_name:
                    stats["material_unresolved"] += 1

                # Handle value_list serialization
                value_list = None
                if rec.value_list is not None:
                    value_list = json.dumps(rec.value_list, ensure_ascii=False)

                if mode == "append-safe":
                    # Check if exists
                    cur.execute("SELECT 1 FROM parameters WHERE id = %s", (rec.id,))
                    if cur.fetchone():
                        stats["skipped"] += 1
                        continue

                cur.execute(
                    """
                    INSERT INTO parameters (
                        id, name, name_en, name_zh, symbol,
                        category, subcategory,
                        value_type, value_scalar, value_min, value_max,
                        value_expr, value_list, value_text, value_str,
                        unit, uncertainty,
                        material_id, material_raw,
                        temperature_k, temperature_str,
                        burnup_range, method,
                        confidence, source_file, equation, notes
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s::jsonb, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        name_en = COALESCE(EXCLUDED.name_en, parameters.name_en),
                        symbol = COALESCE(EXCLUDED.symbol, parameters.symbol),
                        category = EXCLUDED.category,
                        value_type = EXCLUDED.value_type,
                        value_scalar = EXCLUDED.value_scalar,
                        value_min = EXCLUDED.value_min,
                        value_max = EXCLUDED.value_max,
                        value_expr = EXCLUDED.value_expr,
                        value_list = EXCLUDED.value_list,
                        value_text = EXCLUDED.value_text,
                        value_str = EXCLUDED.value_str,
                        unit = COALESCE(EXCLUDED.unit, parameters.unit),
                        material_id = COALESCE(EXCLUDED.material_id, parameters.material_id),
                        material_raw = EXCLUDED.material_raw,
                        temperature_k = COALESCE(EXCLUDED.temperature_k, parameters.temperature_k),
                        confidence = EXCLUDED.confidence,
                        notes = COALESCE(EXCLUDED.notes, parameters.notes)
                    """,
                    (
                        rec.id, rec.name, rec.name_en, rec.name_zh, rec.symbol,
                        rec.category, rec.subcategory,
                        rec.value_type, rec.value_scalar, rec.value_min, rec.value_max,
                        rec.value_expr, value_list, rec.value_text, rec.value_str,
                        rec.unit, rec.uncertainty,
                        material_id, rec.material_raw,
                        rec.temperature_k, rec.temperature_str,
                        rec.burnup_range, rec.method,
                        rec.confidence, rec.source_file, rec.equation, rec.notes,
                    ),
                )
                if cur.rowcount > 0:
                    stats["inserted"] += 1

            except Exception as e:
                stats["errored"] += 1
                if stats["errored"] <= 5:
                    stats["errors"].append(f"{rec.id}: {str(e)[:200]}")

    return stats
