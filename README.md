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

## 数据库 Schema

- **materials** — 材料主表（89 种标准材料 + 367 个别名）
- **parameters** — 参数主表（6750 条，支持 5 种值类型）
- **literature** — 文献表（120+ 篇）
- **categories** — 参数分类字典（36 个分类）
- **terminology** — 中英术语表（54 条，支持中文搜索）
- **material_aliases** — 材料别名映射
- **audit_log** — 审计日志

## 目录结构

```
NFMD/
├── plans/
│   ├── database-platform-plan.md   # 详细计划文档
│   ├── schema_v2.sql               # PostgreSQL DDL
│   └── material-alias-map.json     # 材料规范化映射
├── data/
│   └── fuel_swelling_wiki/         # 知识库数据（不纳入版本控制）
├── scripts/                         # ETL 和工具脚本
├── docs/                            # 文档
└── README.md
```

## 技术栈

- **数据库**: Supabase (PostgreSQL 16)
- **全文搜索**: PostgreSQL tsvector + 术语表中文转英文
- **前端原型**: 飞书多维表格
- **ETL**: Python 3.14
- **知识库**: llm-wiki 技能体系

## License

MIT
