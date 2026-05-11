# NFMD Database Safety Rules

## 🔴 Absolute Prohibitions

| Operation | Reason |
|-----------|--------|
| `DROP TABLE` / `DROP DATABASE` | Irreversible data loss |
| `TRUNCATE` / `TRUNCATE TABLE` | Bypasses audit, cannot recover |
| `DELETE FROM table` (without `WHERE`) | Wipes entire table |
| `UPDATE table SET col=val` (without `WHERE`) | Overwrites every row |

**2026-05-11 incident**: A sub-agent executed `TRUNCATE TABLE categories` which caused all quality remediation work to be rolled back. This file exists to prevent recurrence.

## 🟡 Requires Explicit Approval

- `DELETE` / `UPDATE` affecting > 100 rows
- `ALTER TABLE` / schema changes
- Creating or replacing triggers / functions
- Any operation on `materials`, `categories`, or `literature` tables that modifies > 1 row at a time

## ✅ Safe Operations

- `SELECT` queries (any complexity)
- `EXPLAIN ANALYZE`
- `CREATE TABLE AS SELECT` (temp tables)
- `INSERT INTO SELECT` (new data only)

## Pre-flight Checklist

Before any write operation:

1. **COUNT first**: `SELECT COUNT(*) FROM table WHERE <condition>`
2. **Preview**: `SELECT ... WHERE <condition> LIMIT 5`
3. **Verify backup exists** in `backups/` or Supabase dashboard
4. **Wrap repairs** in `BEGIN; ... COMMIT;` (so you can `ROLLBACK;` if something goes wrong)

## Sub-agent Rules

Any sub-agent performing NFMD database operations **must**:

1. Load the `nfmd-db-ops` skill first
2. Follow the prohibitions above
3. Use transactions for all write operations
4. Report affected row counts before and after

## Known Schemas

| Table | Row Count | Business Key / Notes |
|-------|-----------|---------------------|
| `parameters` | 17,000+ | Business key: `(name, material_id, category, value_type, value_scalar, unit)` |
| `categories` | 47 | `param_count` auto-maintained by `trg_category_param_count` trigger |
| `literature` | 163 | `parameter_count` manually maintained |
| `materials` | 89 | FK target for `parameters.material_id` |
| `material_aliases` | 367 | Maps non-standard names to `materials.id` |
| `audit_log` | growing | Append-only audit trail |
| `terminology` | 54 | Static Chinese-English term mapping |
