"""Configuration for NFMD ETL pipeline.

Database URL is read from the NFMD_DB_URL environment variable.
Falls back to the standard local Supabase connection for development.
"""

import os

# Default: local Supabase development instance
_LOCAL_SUPABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

DB_URL = os.environ.get("NFMD_DB_URL", _LOCAL_SUPABASE_URL)

BATCH_SIZE = 500
