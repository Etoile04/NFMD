"""
NFMD API — 轻量 FastAPI 层
暴露数据库 RPC 函数和核心查询为 REST API

Database 模块持有连接生命周期与行→dict 整形（ADR-0002：依赖只接受
不创建）；SQL 字面量与参数占位符留在端点调用点，execute 一律
"字面量 + %s" 形态，可被安全门禁机检。连接级失败统一翻译为 503。
启动：uv run uvicorn etl.api:app
"""

from collections.abc import Iterator
from functools import lru_cache

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel

from etl.config import Settings


@lru_cache
def get_settings() -> Settings:
    """Application settings — built once; tests override via dependency_overrides."""
    return Settings.from_env()


class Database:
    """连接生命周期 + dict 行整形的唯一持有者。

    调用方约定：``with db.cursor() as cur: cur.execute("<literal SQL>", params)``
    —— 每条 SQL 以字面量出现在调用点（单行，与 execute 同行），值一律经
    占位符绑定。
    """

    def __init__(self, db_url: str) -> None:
        self._conn = psycopg.connect(db_url, autocommit=True, row_factory=dict_row)

    def cursor(self):
        return self._conn.cursor()

    def close(self) -> None:
        self._conn.close()


def get_database(settings: Settings = Depends(get_settings)) -> Iterator[Database]:
    """Per-request Database; swap the adapter (fake/pool) at this seam."""
    db = Database(settings.db_url)
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    title="NFMD API",
    description="核燃料材料参数知识库 REST API",
    version="0.1.0",
)


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(psycopg.InterfaceError)
async def database_unavailable(_: Request, __: Exception) -> JSONResponse:
    """连接级失败 → 503（暂时不可用，重试可愈）；其余 psycopg 错误走默认 500。"""
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


# --- Models ---
class StatsResponse(BaseModel):
    total_parameters: int
    total_materials: int
    total_literature: int
    total_categories: int
    params_by_confidence: dict
    params_by_type: dict
    top_materials: list


class ParameterResult(BaseModel):
    id: str
    name: str | None = None
    name_en: str | None = None
    symbol: str | None = None
    category: str | None = None
    subcategory: str | None = None
    value_type: str | None = None
    value_scalar: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_expr: str | None = None
    value_str: str | None = None
    unit: str | None = None
    material_name: str | None = None
    material_raw: str | None = None
    temperature_k: float | None = None
    confidence: str | None = None
    source_file: str | None = None
    rank: float | None = None


class MaterialInfo(BaseModel):
    name: str
    material_type: str | None = None
    param_count: int = 0


class CategoryInfo(BaseModel):
    category: str
    category_zh: str | None = None
    param_count: int = 0
    material_count: int = 0
    avg_confidence: float | None = None


# --- Endpoints ---

@app.get("/", tags=["meta"])
def root():
    return {"name": "NFMD API", "version": "0.1.0", "docs": "/docs"}


@app.get("/stats", response_model=StatsResponse, tags=["meta"])
def stats(db: Database = Depends(get_database)):
    """数据库总览统计"""
    with db.cursor() as cur:
        cur.execute("SELECT stats_overview() AS stats_overview")
        row = cur.fetchone()
    if row and row["stats_overview"]:
        return row["stats_overview"]
    raise HTTPException(500, "stats_overview returned no data")


@app.get("/search", response_model=list[ParameterResult], tags=["parameters"])
def search_parameters(
    q: str = Query(..., description="搜索关键词（支持中英文）"),
    category: str | None = Query(None, description="分类过滤"),
    material: str | None = Query(None, description="材料过滤"),
    confidence: str | None = Query(None, description="置信度过滤 (high/medium/low)"),
    limit: int = Query(50, ge=1, le=200, description="返回数量上限"),
    db: Database = Depends(get_database),
):
    """全文搜索参数（中文术语自动翻译为英文后搜索）"""
    with db.cursor() as cur:
        cur.execute("SELECT * FROM search_parameters(%s, %s, %s, %s, %s)", (q, category, material, confidence, limit))
        return cur.fetchall()


@app.get("/parameters", response_model=list[ParameterResult], tags=["parameters"])
def list_parameters(
    material: str | None = Query(None),
    category: str | None = Query(None),
    confidence: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_database),
):
    """列出参数，支持过滤和分页（NULL-guard 谓词：未提供的过滤项恒真）"""
    with db.cursor() as cur:
        cur.execute("SELECT p.id, p.name, p.name_en, p.symbol, p.category, p.subcategory, p.value_type, p.value_scalar, p.value_min, p.value_max, p.value_expr, p.value_str, p.unit, m.name AS material_name, p.material_raw, p.temperature_k, p.confidence, p.source_file FROM parameters p LEFT JOIN materials m ON p.material_id = m.id WHERE (%s::text IS NULL OR m.name = %s) AND (%s::text IS NULL OR p.category = %s) AND (%s::text IS NULL OR p.confidence = %s) ORDER BY m.name, p.category, p.name LIMIT %s OFFSET %s", (material, material, category, category, confidence, confidence, limit, offset))
        return cur.fetchall()


@app.get("/parameters/{param_id}", response_model=ParameterResult, tags=["parameters"])
def get_parameter(param_id: str, db: Database = Depends(get_database)):
    """获取单条参数详情"""
    with db.cursor() as cur:
        cur.execute("SELECT p.id, p.name, p.name_en, p.symbol, p.category, p.subcategory, p.value_type, p.value_scalar, p.value_min, p.value_max, p.value_expr, p.value_str, p.unit, m.name AS material_name, p.material_raw, p.temperature_k, p.confidence, p.source_file FROM parameters p LEFT JOIN materials m ON p.material_id = m.id WHERE p.id = %s", (param_id,))
        row = cur.fetchone()
    if row:
        return row
    raise HTTPException(404, f"Parameter '{param_id}' not found")


@app.get("/materials", response_model=list[MaterialInfo], tags=["materials"])
def list_materials(
    type: str | None = Query(None, description="材料类型过滤"),
    has_params: bool | None = Query(None, description="只列出有参数的材料"),
    db: Database = Depends(get_database),
):
    """列出所有材料（has_params 为 true 时仅保留有参数者）"""
    with db.cursor() as cur:
        cur.execute("SELECT m.name, m.material_type, COUNT(p.id)::int AS param_count FROM materials m LEFT JOIN parameters p ON p.material_id = m.id WHERE (%s::text IS NULL OR m.material_type = %s) GROUP BY m.name, m.material_type HAVING (%s::bool IS NOT TRUE OR COUNT(p.id) > 0) ORDER BY param_count DESC, m.name", (type, type, has_params))
        return cur.fetchall()


@app.get("/categories", response_model=list[CategoryInfo], tags=["categories"])
def list_categories(db: Database = Depends(get_database)):
    """列出分类统计"""
    with db.cursor() as cur:
        cur.execute("SELECT * FROM v_params_by_category")
        return cur.fetchall()


# --- Run directly ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8900)
