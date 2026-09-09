#!/usr/bin/env python3
"""CLI entry point for the ETL pipeline."""

import argparse
import os
import time

import psycopg

from etl.config import Settings
from etl.extract import extract_records
from etl.io_utils import create_run_dir, write_json, write_jsonl
from etl.load import LoadFatalError, load_records
from etl.logging_config import get_logger
from etl.normalize import MaterialNormalizer
from etl.transform import transform_records
from etl.validate import validate_records

logger = get_logger(__name__)


# Default alias map (relative to NFMD project root)
DEFAULT_ALIAS_MAP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plans/material-alias-map.json"
)


def run_pipeline(
    mode: str,
    source_dir: str,
    alias_map: str,
    run_id: str | None = None,
    settings: Settings | None = None,
):
    """Execute the full ETL pipeline."""
    settings = settings or Settings.from_env()
    start = time.time()

    # Create run directory
    if not run_id:
        run_id, run_dir = create_run_dir(base_dir=settings.runs_base)
    else:
        run_dir = os.path.join(settings.runs_base, run_id)
        os.makedirs(run_dir, exist_ok=True)

    logger.info("NFMD ETL Pipeline")
    logger.info("Mode: %s", mode)
    logger.info("Run ID: %s", run_id)
    logger.info("Source: %s", source_dir)
    logger.info("Run dir: %s", run_dir)

    # Write run metadata
    meta = {
        "run_id": run_id,
        "mode": mode,
        "source_dir": source_dir,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # === STAGE 1: EXTRACT ===
    logger.info("Stage 1: Extract")
    records = list(extract_records(source_dir))
    logger.info("Extracted: %d records", len(records))

    extracted_path = os.path.join(run_dir, "01-extracted.jsonl")
    write_jsonl(extracted_path, [r.to_dict() for r in records])

    if not records:
        logger.warning("No records extracted. Aborting.")
        meta["status"] = "empty"
        write_json(os.path.join(run_dir, "run-meta.json"), meta)
        return

    # === STAGE 2: VALIDATE ===
    logger.info("Stage 2: Validate")
    valid, errored, issues = validate_records(records, run_id)

    warn_count = sum(1 for i in issues if i.severity == "warn")
    fatal_count = sum(1 for i in issues if i.severity == "fatal")

    logger.info("Valid: %d", len(valid))
    logger.info("Errored: %d", len(errored))
    logger.info("Warnings: %d", warn_count)
    logger.info("Fatals: %d", fatal_count)

    # Save artifacts
    validated_path = os.path.join(run_dir, "02-validated.jsonl")
    write_jsonl(validated_path, [r.to_dict() for r in valid])

    issues_path = os.path.join(run_dir, "02-issues.jsonl")
    write_jsonl(issues_path, [i.to_dict() for i in issues])

    if fatal_count > 0:
        logger.fatal("Aborting due to fatal issues.")
        meta["status"] = "fatal"
        meta["fatal_count"] = fatal_count
        write_json(os.path.join(run_dir, "run-meta.json"), meta)
        return

    # === STAGE 3: TRANSFORM ===
    logger.info("Stage 3: Transform")
    mat_norm = MaterialNormalizer(alias_map)
    transformed = transform_records(valid, mat_norm)

    # Stats
    resolved = sum(1 for t in transformed if t.material_name)
    unresolved = sum(1 for t in transformed if not t.material_name and t.material_raw)
    logger.info("Transformed: %d", len(transformed))
    logger.info("Materials resolved: %d", resolved)
    logger.info("Materials unresolved: %d", unresolved)

    transformed_path = os.path.join(run_dir, "03-transformed.jsonl")
    write_jsonl(transformed_path, [t.to_dict() for t in transformed])

    # === STAGE 4: LOAD (or dry-run summary) ===
    summary = {}

    if mode == "dry-run":
        logger.info("Stage 4: Dry-run (no database writes)")
        summary = _dry_run_summary(records, valid, errored, issues, transformed)
    else:
        logger.info("Stage 4: Load (mode=%s)", mode)
        try:
            with psycopg.connect(settings.db_url) as conn:
                load_stats = load_records(transformed, conn, mode=mode, batch_size=settings.batch_size)
        except LoadFatalError as e:
            summary = {
                "mode": mode,
                "records_transformed": len(transformed),
                "records_fatal": fatal_count,
                **e.stats.to_dict(),
                "fatal_error": str(e),
            }
            write_json(os.path.join(run_dir, "04-load-summary.json"), summary)
            meta["status"] = "fatal"
            meta["fatal_error"] = str(e)
            meta["elapsed_seconds"] = round(time.time() - start, 1)
            write_json(os.path.join(run_dir, "run-meta.json"), meta)
            logger.fatal("Load aborted (fatal): %s", e)
            raise SystemExit(1) from e
        summary = {
            "source_files": len({r.source_file for r in records}),
            "records_extracted": len(records),
            "records_valid": len(valid),
            "records_warn": warn_count,
            "records_error": len(errored),
            "records_fatal": fatal_count,
            **load_stats.to_dict(),
        }
        logger.info("Inserted: %d", load_stats.parameters_inserted)
        logger.info("Updated: %d", load_stats.parameters_updated)
        logger.info("Skipped: %d", load_stats.parameters_skipped)
        logger.info("Errored: %d", load_stats.parameters_errored)

    # Save summary
    summary_path = os.path.join(run_dir, "04-load-summary.json")
    write_json(summary_path, summary)

    # Final metadata
    elapsed = time.time() - start
    meta["status"] = "completed"
    meta["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta["elapsed_seconds"] = round(elapsed, 1)
    write_json(os.path.join(run_dir, "run-meta.json"), meta)

    # Print top error codes
    if issues:
        code_counts = {}
        for iss in issues:
            if iss.severity in ("error", "warn"):
                key = f"{iss.severity}:{iss.code}"
                code_counts[key] = code_counts.get(key, 0) + 1
        logger.info("Top issue codes:")
        for key, count in sorted(code_counts.items(), key=lambda x: -x[1])[:10]:
            logger.info("  %s: %d", key, count)

    # Print unmapped materials
    if unresolved > 0:
        unmapped = {}
        for t in transformed:
            if not t.material_name and t.material_raw:
                unmapped[t.material_raw] = unmapped.get(t.material_raw, 0) + 1
        logger.info("Unmapped materials (%d):", len(unmapped))
        for mat, count in sorted(unmapped.items(), key=lambda x: -x[1])[:20]:
            logger.info("  %s: %d", mat, count)

    logger.info("Done in %.1fs — artifacts in %s", elapsed, run_dir)


def _dry_run_summary(
    all_records, valid, errored, issues, transformed
) -> dict:
    """Generate summary for dry-run mode."""
    # Top error codes
    code_counts = {}
    for iss in issues:
        code_counts[iss.code] = code_counts.get(iss.code, 0) + 1

    # Unmapped materials
    unmapped = {}
    for t in transformed:
        if not t.material_name and t.material_raw:
            unmapped[t.material_raw] = unmapped.get(t.material_raw, 0) + 1

    return {
        "mode": "dry-run",
        "source_files": len({r.source_file for r in all_records}),
        "records_extracted": len(all_records),
        "records_valid": len(valid),
        "records_error": len(errored),
        "records_warn": sum(1 for i in issues if i.severity == "warn"),
        "records_fatal": sum(1 for i in issues if i.severity == "fatal"),
        "top_error_codes": dict(sorted(code_counts.items(), key=lambda x: -x[1])[:15]),
        "unmapped_materials": dict(sorted(unmapped.items(), key=lambda x: -x[1])[:30]),
        "material_resolved": sum(1 for t in transformed if t.material_name),
        "material_unresolved": sum(1 for t in transformed if not t.material_name and t.material_raw),
        "value_type_distribution": {
            vt: sum(1 for t in transformed if t.value_type == vt)
            for vt in ["scalar", "range", "expression", "list", "text"]
        },
    }


def main():
    """Parse CLI arguments and launch the ETL pipeline."""
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="NFMD ETL Pipeline")
    parser.add_argument(
        "--mode",
        choices=["dry-run", "append-safe", "replace-run"],
        default="dry-run",
        help="Run mode (default: dry-run)",
    )
    parser.add_argument(
        "--source-dir",
        default=settings.default_source_dir,
        help="Source parameters directory",
    )
    parser.add_argument(
        "--alias-map",
        default=DEFAULT_ALIAS_MAP,
        help="Material alias map JSON file",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Resume/reuse an existing run ID",
    )

    args = parser.parse_args()
    run_pipeline(args.mode, args.source_dir, args.alias_map, args.run_id)


if __name__ == "__main__":
    main()
