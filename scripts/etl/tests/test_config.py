"""Tests for the Settings module (scripts/etl/config.py)."""

import os

import pytest
from config import DEFAULT_DB_URL, Settings


class TestDefaults:
    """from_env with an empty environment yields the documented defaults."""

    def test_default_db_url_is_credentialless_docker_url(self):
        settings = Settings.from_env(env={})
        assert settings.db_url == DEFAULT_DB_URL
        assert settings.db_url == "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

    def test_default_batch_size(self):
        assert Settings.from_env(env={}).batch_size == 500

    def test_default_source_dir(self):
        expected = os.path.join(
            os.path.expanduser("~"),
            ".openclaw/workspace/data/nuclear-materials-wiki/parameters",
        )
        assert Settings.from_env(env={}).default_source_dir == expected

    def test_default_runs_base(self):
        assert Settings.from_env(env={}).runs_base == "data/imports/runs"


class TestFromEnvOverrides:
    """Each supported env var overrides exactly its own field."""

    def test_db_url_override(self):
        env = {"NFMD_DB_URL": "postgresql://user:pw@db.example.com:5432/nfmd"}
        assert Settings.from_env(env=env).db_url == env["NFMD_DB_URL"]

    def test_batch_size_override(self):
        assert Settings.from_env(env={"NFMD_BATCH_SIZE": "250"}).batch_size == 250

    def test_source_dir_override(self):
        env = {"NFMD_SOURCE_DIR": "/data/wiki/parameters"}
        assert Settings.from_env(env=env).default_source_dir == "/data/wiki/parameters"

    def test_runs_base_override(self):
        env = {"NFMD_RUNS_BASE": "/tmp/nfmd-runs"}
        assert Settings.from_env(env=env).runs_base == "/tmp/nfmd-runs"

    def test_empty_string_env_vars_are_ignored(self):
        settings = Settings.from_env(env={"NFMD_DB_URL": "", "NFMD_SOURCE_DIR": ""})
        assert settings.db_url == DEFAULT_DB_URL
        assert settings.default_source_dir == Settings.from_env(env={}).default_source_dir

    def test_explicit_env_dict_is_not_os_environ(self, monkeypatch):
        monkeypatch.setenv("NFMD_DB_URL", "postgresql://from-os-environ/db")
        settings = Settings.from_env(env={})
        assert settings.db_url == DEFAULT_DB_URL

    def test_non_numeric_batch_size_raises(self):
        with pytest.raises(ValueError):
            Settings.from_env(env={"NFMD_BATCH_SIZE": "not-a-number"})


class TestImmutability:
    """Settings is frozen — construct a new one instead of mutating."""

    def test_assignment_raises(self):
        settings = Settings.from_env(env={})
        with pytest.raises(Exception):  # noqa: B017 — dataclasses.FrozenInstanceError
            settings.db_url = "postgresql://elsewhere/db"
