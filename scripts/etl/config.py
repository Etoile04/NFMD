"""Configuration for NFMD.

Single Settings module owning all configuration knowledge. Entry points
construct it once via ``Settings.from_env()`` and pass it (or its fields)
down; nothing below the entry point reads the environment. The default
database URL targets the local Docker PostgreSQL from ``.env.example`` and
carries no real credentials — role passwords live only in the environment.
"""

import os
from dataclasses import dataclass

# Dev default: local Docker PostgreSQL (README Quick Start / .env.example)
DEFAULT_DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

# Batch size for parameter loading (kept as a constant for transitional
# callers; Settings.batch_size is the canonical surface)
BATCH_SIZE = 500


@dataclass(frozen=True)
class Settings:
    """Frozen configuration snapshot — construct a new one instead of mutating."""

    db_url: str = DEFAULT_DB_URL
    batch_size: int = BATCH_SIZE
    default_source_dir: str = os.path.join(
        os.path.expanduser("~"),
        ".openclaw/workspace/data/nuclear-materials-wiki/parameters",
    )
    runs_base: str = "data/imports/runs"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        """Build Settings from a mapping; ``os.environ`` when omitted.

        Empty-string values are ignored so a shell ``export NFMD_DB_URL=``
        does not blank out a default.
        """
        source = os.environ if env is None else env
        overrides: dict = {}
        if source.get("NFMD_DB_URL"):
            overrides["db_url"] = source["NFMD_DB_URL"]
        if source.get("NFMD_BATCH_SIZE"):
            overrides["batch_size"] = int(source["NFMD_BATCH_SIZE"])
        if source.get("NFMD_SOURCE_DIR"):
            overrides["default_source_dir"] = source["NFMD_SOURCE_DIR"]
        if source.get("NFMD_RUNS_BASE"):
            overrides["runs_base"] = source["NFMD_RUNS_BASE"]
        return cls(**overrides)
