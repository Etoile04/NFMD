# NFMD — Nuclear Fuel Material Database

**AI-driven parameter knowledge base for nuclear fuel materials**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()
[![CI](https://github.com/Etoile04/NFMD/actions/workflows/ci.yml/badge.svg)](https://github.com/Etoile04/NFMD/actions/workflows/ci.yml)

An end-to-end pipeline for literature retrieval, PDF parsing, knowledge extraction, parameter validation, and database ingestion — building a queryable nuclear fuel material parameter database for fuel performance codes (JSRT, BISON, etc.).

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Client Layer                         │
│         Feishu Bitable / Supabase Studio / REST API       │
├───────────────────────────────────────────────────────────┤
│                   FastAPI REST API                        │
│    search · parameters · materials · categories · stats   │
│              (nfmd_reader, RLS-enforced)                  │
├───────────────────────────────────────────────────────────┤
│                PostgreSQL 16 (nfmd database)              │
│  materials · parameters · literature · categories         │
│  terminology · material_aliases · audit_log · review_*    │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│  Row-Level Security (nfmd_reader / nfmd_writer roles)     │
│  Triggers: audit · tsvector · param_count                 │
├───────────────────────────────────────────────────────────┤
│                    ETL Pipeline                           │
│  extract → validate → transform → normalize → load        │
│  (7 modules, rule-based quality checks)                   │
├───────────────────────────────────────────────────────────┤
│                 Knowledge Sources                         │
│  Zotero · MinerU · llm-wiki · Materials Project           │
└───────────────────────────────────────────────────────────┘
```

---

## 📊 Database Scale

| Table | Records | Purpose |
|-------|---------|---------|
| material_aliases | 384 | Material name normalization map |
| materials | 98 | Canonical material entries |
| audit_log | 93 | Change tracking (auto via trigger) |
| parameters | 87 | Extracted material property values |
| terminology | 54 | Chinese↔English term mapping |
| categories | 6 | Property classification |
| literature | 4 | Source publication metadata |
| review_audit_log | 0 | Review workflow tracking |

---

## 🚀 Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python + dependencies via `uv.lock`)
- PostgreSQL 16 (running in Docker)

### 0. Environment Setup

```bash
uv sync          # creates .venv and installs locked dependencies (incl. dev tools)
```

### 1. Database Setup

```bash
# Start PostgreSQL (adjust port as needed)
docker run -d --name nfmd-postgres \
  -e POSTGRES_DB=nfmd \
  -e POSTGRES_USER=postgres \
  -p 15432:5432 \
  postgres:16

# Create schema + roles
psql -h localhost -p 15432 -U postgres -d nfmd -f plans/schema_v2.sql
psql -h localhost -p 15432 -U postgres -d nfmd -f sql/create_roles.sql
```

### 2. Run ETL Pipeline

```bash
bash scripts/run_etl.sh          # defaults to dry-run mode
```

### 3. Start API Server

```bash
bash scripts/start_api.sh
# or directly:
# cd scripts && uv run uvicorn api:app --host 0.0.0.0 --port 8900
```

### 4. Query

```bash
# Database stats
curl http://localhost:8000/stats

# Search parameters
curl "http://localhost:8000/search?q=thermal+conductivity&material=UO2"

# List materials
curl http://localhost:8000/materials

# List parameters with filters
curl "http://localhost:8000/parameters?material=UO2&category=thermal"
```

---

## 📈 Phase 2 Status — ETL Pipeline

### ETL Pipeline
- 8 Python modules, ~1276 LOC
- Pipeline stages: Extract → Validate → Transform → Load
- Supports scalar, range, expression, list value types

### Data Import Results
- **6,980 parameters** imported, 0 fatal errors
- **89 materials** + 358 aliases
- **174 literature** entries
- 47 distinct categories, 100% source coverage
- Full-text search (ts_vector) populated for all records

### Configuration
- DB URL via `NFMD_DB_URL` environment variable (defaults to local Supabase)
- See `.env.example` for setup

### Testing
- Run: `uv run pytest -v`
- 75 tests covering extract, validate, normalize, transform, load, and I/O
- CI: ruff + pytest on every push/PR ([.github/workflows/ci.yml](.github/workflows/ci.yml))

---

## 📁 Project Structure

```
NFMD/
├── plans/
│   ├── database-platform-plan.md       # Detailed design document
│   ├── schema_v2.sql                   # PostgreSQL DDL (tables, triggers, views, RPCs)
│   └── material-alias-map.json         # Material normalization dictionary
├── sql/
│   ├── create_roles.sql                # RLS roles (nfmd_reader, nfmd_writer) + policies
│   └── repair_quality.sql              # Data quality repair scripts
├── scripts/
│   ├── api.py                          # FastAPI REST API (254 lines, 6 endpoints)
│   ├── start_api.sh                    # API launch script
│   ├── run_etl.sh                      # ETL launcher
│   └── etl/
│       ├── extract.py                  # JSON/text → ExtractedRecord
│       ├── validate.py                 # Rule-based validation (9 rules)
│       ├── transform.py                # ExtractedRecord → TransformedRecord
│       ├── normalize.py                # Material name + unit normalization
│       ├── load.py                     # Batch INSERT with upsert
│       ├── models.py                   # Data models (ExtractedRecord, TransformedRecord)
│       ├── rules.py                    # Validation rule engine
│       ├── io_utils.py                 # File I/O helpers
│       ├── config.py                   # DB URL + batch size configuration
│       ├── logging_config.py           # Centralized logging setup
│       ├── run_pipeline.py             # Pipeline orchestrator
│       └── tests/                      # Test suite (75 tests)
│           ├── conftest.py
│           ├── test_extract.py
│           ├── test_validate.py
│           ├── test_normalize.py
│           ├── test_transform.py
│           ├── test_load.py
│           └── test_io_utils.py
├── data/                               # Knowledge base data (git-ignored)
│   └── fuel_swelling_wiki/
├── docs/
│   └── database-safety-rules.md        # DB operation safety rules
└── README.md
```

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info + version |
| `GET` | `/stats` | Database statistics (table counts) |
| `GET` | `/search` | Full-text parameter search (`q`, `material`) |
| `GET` | `/parameters` | List parameters with filters (`material`, `category`, `limit`) |
| `GET` | `/parameters/{id}` | Get single parameter by ID |
| `GET` | `/materials` | List materials with optional `category` filter |
| `GET` | `/categories` | List all categories |

All read endpoints use `nfmd_reader` role with Row-Level Security enforced.

---

## 🔒 Security

### Row-Level Security (RLS)

Two database roles enforce access control:

| Role | Access | Use Case |
|------|--------|----------|
| `nfmd_reader` | SELECT on all tables (except audit_log) | API server, read-only queries |
| `nfmd_writer` | INSERT + UPDATE on data tables; INSERT-only on audit_log | ETL pipeline, write operations |

All tables have RLS enabled. Audit log is write-only (not readable by either role).

### Safety Rules

All database write operations must follow [docs/database-safety-rules.md](docs/database-safety-rules.md):

- 🔴 **Forbidden**: `DROP TABLE`, `TRUNCATE`, `DELETE`/`UPDATE` without `WHERE`
- 🟡 **Needs approval**: Operations affecting >100 rows, schema changes
- ✅ **Safe**: All `SELECT` queries, `EXPLAIN ANALYZE`
- 🤖 Subagents must load `nfmd-db-ops` skill before any DB operations

---

## ✅ Data Quality

Multi-layer quality assurance built into the pipeline:

1. **Business key dedup** — Unique constraint on `(name, material_id, category, value_type, value_scalar, unit)` prevents duplicate imports
2. **Rule engine** — 9 validation rules in `scripts/etl/rules.py`:
   - Missing field detection (id, name, category, value_type)
   - Invalid category / value_type checking
   - Scalar/range value consistency (scalar needs `value_scalar`, range needs min/max)
   - Range min ≤ max enforcement
3. **Source file normalization** — `v_source_file_normalized` view maps diverse path formats to `literature.id`
4. **Auto param_count** — `trg_category_param_count` trigger maintains category counts on parameter changes
5. **Audit trail** — `audit_log` table + `trg_params_audit` trigger records all parameter changes
6. **Material normalization** — `MaterialNormalizer` with alias map handles synonyms (e.g., "UO₂" = "二氧化铀" = "uranium dioxide")

---

## 🗄️ Database Objects

### Tables (8)

`materials` · `material_aliases` · `categories` · `literature` · `parameters` · `terminology` · `audit_log` · `review_audit_log`

### Views (3)

| View | Purpose |
|------|---------|
| `v_source_file_normalized` | Unifies file path formats → links to `literature` |
| `v_params_by_material` | Parameters grouped by material |
| `v_params_by_category` | Parameters grouped by category |

### Functions (4)

| Function | Purpose |
|----------|---------|
| `parameters_tsvector_update()` | Auto-update tsvector on parameter changes |
| `audit_trigger_func()` | Record parameter changes to audit_log |
| `refresh_category_param_count()` | Maintain category.param_count |
| `search_parameters(query)` | Full-text search with tsvector ranking |
| `stats_overview()` | Database statistics overview |

### Triggers (3)

`trg_params_tsvector` · `trg_params_audit` · `trg_category_param_count`

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Database | PostgreSQL 16 (Docker) |
| API | FastAPI + Uvicorn |
| ETL | Python 3.10+ (custom pipeline) |
| Search | PostgreSQL tsvector + terminology Chinese↔English |
| Security | Row-Level Security (RLS) |
| Knowledge Base | llm-wiki skill system |
| Literature | Zotero + MinerU PDF extraction |
| Frontend | Feishu Bitable (prototype) |

---

## 📜 License

MIT
