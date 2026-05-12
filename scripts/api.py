"""
NFMD API — 轻量 FastAPI 层
暴露数据库 RPC 函数和核心查询为 REST API
使用 nfmd_reader 角色连接（RLS 强制生效）
"""

import os
from typing import Optional

import psycopg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# --- Config ---
DB_URL = os.environ.get(
    "NFMD_DB_URL",
    "postgresql://nfmd_reader:nfmd_read_2026@127.0.0.1:5432/nfmd",
)
DB_WRITE_URL = os.environ.get(
    "NFMD_DB_WRITE_URL",
    "postgresql://nfmd_writer:nfmd_write_2026@127.0.0.1:5432/nfmd",
)

app = FastAPI(
    title="NFMD API",
    description="核燃料材料参数知识库 REST API",
    version="0.1.0",
)


# --- Helpers ---
def get_db(read_only: bool = True) -> psycopg.Connection:
    url = DB_URL if read_only else DB_WRITE_URL
    return psycopg.connect(url, autocommit=True)


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
    name: Optional[str] = None
    name_en: Optional[str] = None
    symbol: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    value_type: Optional[str] = None
    value_scalar: Optional[float] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_expr: Optional[str] = None
    value_str: Optional[str] = None
    unit: Optional[str] = None
    material_name: Optional[str] = None
    material_raw: Optional[str] = None
    temperature_k: Optional[float] = None
    confidence: Optional[str] = None
    source_file: Optional[str] = None
    rank: Optional[float] = None


class MaterialInfo(BaseModel):
    name: str
    material_type: Optional[str] = None
    param_count: int = 0


class CategoryInfo(BaseModel):
    category: str
    category_zh: Optional[str] = None
    param_count: int = 0
    material_count: int = 0
    avg_confidence: Optional[float] = None


# --- Endpoints ---

@app.get("/", tags=["meta"])
def root():
    return {"name": "NFMD API", "version": "0.1.0", "docs": "/docs"}


@app.get("/stats", response_model=StatsResponse, tags=["meta"])
def stats():
    """数据库总览统计"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stats_overview()")
            row = cur.fetchone()
            if row:
                return row[0]
            raise HTTPException(500, "stats_overview returned no data")
    finally:
        conn.close()


@app.get("/search", response_model=list[ParameterResult], tags=["parameters"])
def search_parameters(
    q: str = Query(..., description="搜索关键词（支持中英文）"),
    category: Optional[str] = Query(None, description="分类过滤"),
    material: Optional[str] = Query(None, description="材料过滤"),
    confidence: Optional[str] = Query(None, description="置信度过滤 (high/medium/low)"),
    limit: int = Query(50, ge=1, le=200, description="返回数量上限"),
):
    """全文搜索参数（中文术语自动翻译为英文后搜索）"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM search_parameters(%s, %s, %s, %s, %s)",
                (q, category, material, confidence, limit),
            )
            cols = [desc[0] for desc in cur.description]
            results = [dict(zip(cols, row)) for row in cur.fetchall()]
            return results
    finally:
        conn.close()


@app.get("/parameters", response_model=list[ParameterResult], tags=["parameters"])
def list_parameters(
    material: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    confidence: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """列出参数，支持过滤和分页"""
    conn = get_db()
    try:
        conditions = []
        params = []
        if material:
            conditions.append("m.name = %s")
            params.append(material)
        if category:
            conditions.append("p.category = %s")
            params.append(category)
        if confidence:
            conditions.append("p.confidence = %s")
            params.append(confidence)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT p.id, p.name, p.name_en, p.symbol,
                           p.category, p.subcategory, p.value_type,
                           p.value_scalar, p.value_min, p.value_max,
                           p.value_expr, p.value_str, p.unit,
                           m.name AS material_name, p.material_raw,
                           p.temperature_k, p.confidence, p.source_file
                    FROM parameters p
                    LEFT JOIN materials m ON p.material_id = m.id
                    {where}
                    ORDER BY m.name, p.category, p.name
                    LIMIT %s OFFSET %s""",
                params,
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


@app.get("/parameters/{param_id}", response_model=ParameterResult, tags=["parameters"])
def get_parameter(param_id: str):
    """获取单条参数详情"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.id, p.name, p.name_en, p.symbol,
                          p.category, p.subcategory, p.value_type,
                          p.value_scalar, p.value_min, p.value_max,
                          p.value_expr, p.value_str, p.unit,
                          m.name AS material_name, p.material_raw,
                          p.temperature_k, p.confidence, p.source_file
                   FROM parameters p
                   LEFT JOIN materials m ON p.material_id = m.id
                   WHERE p.id = %s""",
                (param_id,),
            )
            cols = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            if row:
                return dict(zip(cols, row))
            raise HTTPException(404, f"Parameter '{param_id}' not found")
    finally:
        conn.close()


@app.get("/materials", response_model=list[MaterialInfo], tags=["materials"])
def list_materials(
    type: Optional[str] = Query(None, description="材料类型过滤"),
    has_params: Optional[bool] = Query(None, description="只列出有参数的材料"),
):
    """列出所有材料"""
    conn = get_db()
    try:
        conditions = []
        params = []
        if type:
            conditions.append("m.material_type = %s")
            params.append(type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT m.name, m.material_type,
                           COUNT(p.id)::int AS param_count
                    FROM materials m
                    LEFT JOIN parameters p ON p.material_id = m.id
                    {where}
                    GROUP BY m.name, m.material_type
                    {"HAVING COUNT(p.id) > 0" if has_params else ""}
                    ORDER BY param_count DESC, m.name""",
                params,
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


@app.get("/categories", response_model=list[CategoryInfo], tags=["categories"])
def list_categories():
    """列出分类统计"""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM v_params_by_category")
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# --- Run directly ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8900)
