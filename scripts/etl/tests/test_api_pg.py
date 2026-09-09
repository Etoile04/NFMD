"""Integration tests: API 端点 × 真实 PostgreSQL。

把 Python ↔ SQL RPC 契约（stats_overview / search_parameters /
v_params_by_category）钉在真库上——这是架构评审候选 1 承诺的
"RPC 契约无任何东西钉住" 的补齐。依赖注入只换 get_settings，
端点→Database→psycopg 全链路走真。
"""

import api
import psycopg
import pytest
from config import Settings
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(test_db_url):
    with (
        psycopg.connect(test_db_url) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("INSERT INTO materials (name, material_type) VALUES ('UO2', 'FuelMaterial') ON CONFLICT DO NOTHING")
        cur.execute("SELECT id FROM materials WHERE name = 'UO2'")
        material_id = cur.fetchone()[0]
        cur.execute("INSERT INTO literature (id, title, year, parameter_count) VALUES ('lit-api-1', 'API Integration Paper', 2024, 1) ON CONFLICT (id) DO NOTHING")
        cur.execute("INSERT INTO parameters (id, name, name_en, category, value_type, value_scalar, unit, material_id, source_file, confidence) VALUES ('pg-api-001', '密度', 'density', 'physical', 'scalar', 10.97, 'g/cm³', %s, 'api-paper', 'high') ON CONFLICT (id) DO NOTHING", (material_id,))

    app = api.app
    app.dependency_overrides[api.get_settings] = lambda: Settings(db_url=test_db_url)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(api.get_settings, None)


class TestStatsRpc:
    def test_stats_overview_contract(self, api_client):
        resp = api_client.get("/stats")
        assert resp.status_code == 200
        body = resp.json()
        # RPC 返回 jsonb 的字段面（契约），数值只做关系断言防跨测试脆弱
        assert body["total_parameters"] >= 1
        assert body["total_materials"] >= 1
        assert set(body["params_by_type"]) >= {"scalar"}
        assert any(m["name"] == "UO2" for m in body["top_materials"])


class TestSearchRpc:
    def test_search_finds_seeded_parameter(self, api_client):
        resp = api_client.get("/search", params={"q": "density"})
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert "pg-api-001" in ids

    def test_search_unknown_term_returns_empty(self, api_client):
        resp = api_client.get("/search", params={"q": "zzz-nonexistent-term"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestParameterDetail:
    def test_seeded_parameter_roundtrip(self, api_client):
        resp = api_client.get("/parameters/pg-api-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["material_name"] == "UO2"
        assert body["value_scalar"] == 10.97

    def test_missing_parameter_404(self, api_client):
        assert api_client.get("/parameters/nope-404").status_code == 404


class TestMaterialsEndpoint:
    def test_has_params_returns_seeded_material(self, api_client):
        resp = api_client.get("/materials", params={"has_params": True})
        assert resp.status_code == 200
        names = [m["name"] for m in resp.json()]
        assert "UO2" in names
