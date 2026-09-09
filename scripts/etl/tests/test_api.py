"""Interface tests for the API layer.

Endpoints are exercised through TestClient with a fake Database injected
via dependency_overrides — no live Postgres, no cursor mocks. The fake
satisfies the same small protocol the endpoints consume (cursor/execute/
fetch, dict rows, close).
"""

import contextlib

import pytest
from fastapi.testclient import TestClient

from etl import api
from etl.api import app


class FakeCursor:
    """Implements the cursor protocol endpoints use: execute → fetchone/fetchall."""

    def __init__(self, rows: list, single: dict | None, calls: list) -> None:
        self._rows = rows
        self._single = single
        self._calls = calls

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchone(self):
        return self._single

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeDatabase:
    """In-memory adapter standing in for api.Database."""

    def __init__(self, *, rows=None, single=None):
        self.rows = rows if rows is not None else []
        self.single = single
        self.calls: list[tuple[str, tuple | None]] = []

    def cursor(self):
        return FakeCursor(self.rows, self.single, self.calls)

    def close(self):
        pass


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@contextlib.contextmanager
def use_database(fake: FakeDatabase):
    app.dependency_overrides[api.get_database] = lambda: fake
    yield
    app.dependency_overrides.pop(api.get_database, None)


# ---------------------------------------------------------------------------
# Root / meta
# ---------------------------------------------------------------------------


class TestRoot:
    def test_returns_api_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "NFMD API"
        assert "version" in body


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_returns_rpc_payload(self, client):
        stats_payload = {
            "total_parameters": 42,
            "total_materials": 9,
            "total_literature": 7,
            "total_categories": 5,
            "params_by_confidence": {"high": 42},
            "params_by_type": {"scalar": 42},
            "top_materials": ["UO2"],
        }
        fake = FakeDatabase(single={"stats_overview": stats_payload})
        with use_database(fake):
            resp = client.get("/stats")
        assert resp.status_code == 200
        assert resp.json()["total_parameters"] == 42

    def test_rpc_empty_is_500(self, client):
        fake = FakeDatabase(single=None)
        with use_database(fake):
            resp = client.get("/stats")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_q_is_required(self, client):
        # dependency 先于参数校验解析：注入 fake 避免真连库，验证 422 来自 q 缺失
        with use_database(FakeDatabase()):
            resp = client.get("/search")
        assert resp.status_code == 422

    def test_passes_query_to_rpc(self, client):
        fake = FakeDatabase(rows=[{"id": "p1", "name": "density"}])
        with use_database(fake):
            resp = client.get("/search", params={"q": "thermal conductivity"})
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == "p1"
        sql, params = fake.calls[0]
        assert "search_parameters" in sql
        assert params[0] == "thermal conductivity"

    def test_result_rows_pass_through(self, client):
        fake = FakeDatabase(rows=[])
        with use_database(fake):
            resp = client.get("/search", params={"q": "nothing"})
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# /parameters
# ---------------------------------------------------------------------------


class TestListParameters:
    def test_returns_rows(self, client):
        fake = FakeDatabase(rows=[{"id": "p1", "name": "density"}])
        with use_database(fake):
            resp = client.get("/parameters")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["id"] == "p1"
        assert body[0]["name"] == "density"
        # response_model 补齐缺省字段（None），不剔除
        assert body[0]["unit"] is None

    def test_material_filter_reaches_query_params(self, client):
        fake = FakeDatabase(rows=[])
        with use_database(fake):
            resp = client.get("/parameters", params={"material": "UO2"})
        assert resp.status_code == 200
        _, params = fake.calls[0]
        assert "UO2" in params

    def test_combined_filters_and_pagination(self, client):
        fake = FakeDatabase(rows=[])
        with use_database(fake):
            resp = client.get(
                "/parameters",
                params={"material": "UO2", "category": "thermal", "limit": 10, "offset": 5},
            )
        assert resp.status_code == 200
        _, params = fake.calls[0]
        assert params[-2:] == (10, 5)
        assert "UO2" in params and "thermal" in params


class TestGetParameter:
    def test_found_returns_row(self, client):
        fake = FakeDatabase(single={"id": "p1", "name": "density"})
        with use_database(fake):
            resp = client.get("/parameters/p1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "p1"

    def test_missing_returns_404(self, client):
        fake = FakeDatabase(single=None)
        with use_database(fake):
            resp = client.get("/parameters/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /materials and /categories
# ---------------------------------------------------------------------------


class TestMaterials:
    def test_returns_rows(self, client):
        fake = FakeDatabase(rows=[{"name": "UO2", "material_type": "oxide", "param_count": 3}])
        with use_database(fake):
            resp = client.get("/materials")
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "UO2"

    def test_type_filter_reaches_query(self, client):
        fake = FakeDatabase(rows=[])
        with use_database(fake):
            resp = client.get("/materials", params={"type": "oxide"})
        assert resp.status_code == 200
        _, params = fake.calls[0]
        assert "oxide" in params


class TestCategories:
    def test_returns_rows(self, client):
        fake = FakeDatabase(rows=[{"category": "thermal", "param_count": 12}])
        with use_database(fake):
            resp = client.get("/categories")
        assert resp.status_code == 200
        assert resp.json()[0]["category"] == "thermal"


# ---------------------------------------------------------------------------
# Error translation: connection-level psycopg failures → 503
# ---------------------------------------------------------------------------


class TestDbUnavailable:
    def test_operational_error_maps_to_503(self, client):
        import psycopg

        def broken():
            raise psycopg.OperationalError("connection refused")
            yield  # pragma: no cover

        app.dependency_overrides[api.get_database] = broken
        try:
            resp = client.get("/stats")
        finally:
            app.dependency_overrides.pop(api.get_database, None)
        assert resp.status_code == 503

    def test_interface_error_maps_to_503(self, client):
        import psycopg

        def broken():
            raise psycopg.InterfaceError("connection closed")
            yield  # pragma: no cover

        app.dependency_overrides[api.get_database] = broken
        try:
            resp = client.get("/parameters")
        finally:
            app.dependency_overrides.pop(api.get_database, None)
        assert resp.status_code == 503
