# NFMD — Nuclear Fuel Material Database

AI 驱动的核燃料材料参数知识库，服务于核燃料性能代码（JSRT、BISON 等）的模型参数标定。

## 项目目标

从文献检索、PDF 解析、知识提取、参数校验到比对入库的全流程自动化，最终构建可查询的核燃料材料参数数据库。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                   前端展示层                          │
│         飞书多维表格 / Supabase Studio                │
├─────────────────────────────────────────────────────┤
│                   API 层                             │
│    Supabase REST API (PostgREST) + RPC               │
├─────────────────────────────────────────────────────┤
│                   数据库层 (PostgreSQL)               │
│  materials / parameters / literature / categories    │
│  terminology / material_aliases / audit_log          │
├─────────────────────────────────────────────────────┤
│                   ETL 层                              │
│  JSON → SQL / 增量同步 / 术语转换                    │
├─────────────────────────────────────────────────────┤
│                   知识库层                            │
│  summaries/ (138) / parameters/ (6750) / wiki/        │
├─────────────────────────────────────────────────────┤
│                   外部集成                            │
│  Zotero / MinerU / Supabase / GitHub                 │
└─────────────────────────────────────────────────────┘
```

## Phase 2 Status — ETL Pipeline 完成

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
- Run: `python3 -m pytest scripts/etl/tests/ -v`
- 75 tests covering extract, validate, normalize, transform, load, and I/O

### Database Schema

- **materials** — 材料主表（89 种标准材料 + 358 个别名）
- **parameters** — 参数主表（6,980 条，支持 5 种值类型）
- **literature** — 文献表（174 篇）
- **categories** — 参数分类字典（47 个分类）
- **terminology** — 中英术语表（支持中文搜索）
- **material_aliases** — 材料别名映射
- **audit_log** — 审计日志

### Project Structure

```
NFMD/
├── scripts/etl/          # ETL pipeline
│   ├── extract.py        # JSON → ExtractedRecord
│   ├── validate.py       # Rule-based validation
│   ├── transform.py      # Normalization + mapping
│   ├── load.py           # PostgreSQL UPSERT
│   ├── normalize.py      # Material aliases, units, temp
│   ├── models.py         # Data models
│   ├── rules.py          # Validation rule definitions
│   ├── run_pipeline.py   # CLI entry point
│   ├── config.py         # DB URL configuration
│   ├── logging_config.py # Centralized logging
│   └── tests/            # Test suite (75 tests)
├── data/imports/runs/    # ETL run artifacts
├── plans/                # Design documents
└── docs/                 # Specs and plans
```

## 技术栈

- **数据库**: Supabase (PostgreSQL 16)
- **全文搜索**: PostgreSQL tsvector + 术语表中文转英文
- **前端原型**: 飞书多维表格
- **ETL**: Python 3.14
- **知识库**: llm-wiki 技能体系

## License

MIT
