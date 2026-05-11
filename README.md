# NFMD — Nuclear Fuel Material Database

AI 驱动的核燃料材料参数知识库，服务于核燃料性能代码（JSRT、BISON 等）的模型参数标定。

## 项目目标

从文献检索、PDF 解析、知识提取、参数校验到比对入库的全流程自动化，最终构建可查询的核燃料材料参数数据库。

## 数据库规模

| 表 | 记录数 |
|----|--------|
| parameters | 17,095 |
| materials | 89 |
| literature | 163 |
| categories | 47 |
| material_aliases | 367 |
| terminology | 54 |

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
│  JSON → SQL / 增量同步 / 术语转换 / 去重校验          │
├─────────────────────────────────────────────────────┤
│                   知识库层                            │
│  summaries/ (138) / parameters/ (6750) / wiki/        │
├─────────────────────────────────────────────────────┤
│                   外部集成                            │
│  Zotero / MinerU / Supabase / GitHub                 │
└─────────────────────────────────────────────────────┘
```

## 目录结构

```
NFMD/
├── plans/
│   ├── database-platform-plan.md   # 详细计划文档
│   ├── schema_v2.sql               # PostgreSQL DDL (含质量防护触发器)
│   └── material-alias-map.json     # 材料规范化映射
├── sql/
│   └── repair_quality.sql          # 数据质量修复脚本
├── data/
│   └── fuel_swelling_wiki/         # 知识库数据（不纳入版本控制）
├── scripts/
│   ├── etl/                        # ETL 管线 (extract/transform/load/normalize/validate)
│   └── run_etl.sh                  # ETL 启动脚本
├── docs/
│   └── database-safety-rules.md    # 数据库操作安全规则
└── README.md
```

## 数据质量防护

已实施的多层数据质量保障：

1. **ETL 业务键去重** — `(name, material_id, category, value_type, value_scalar, unit)` 唯一约束，防止重复导入
2. **验证规则** — `scripts/etl/rules.py` + `validate.py` 执行：
   - 泛化名称过滤（避免 "property", "parameter" 等无意义名称入库）
   - `value_type` 一致性校验（scalar 必须有 `value_scalar`，range 必须有 min/max）
   - Range min ≤ max 检查
3. **source_file 标准化** — `v_source_file_normalized` 视图将多种路径格式统一映射到 `literature.id`
4. **param_count 自动维护** — `trg_category_param_count` 触发器在参数增删改时自动更新对应分类的计数
5. **审计日志** — `audit_log` 表 + `trg_params_audit` 触发器记录所有参数变更

## 安全规则

所有数据库写操作必须遵循 [docs/database-safety-rules.md](docs/database-safety-rules.md) 中的规则。核心要点：

- 🔴 **禁止**: `DROP TABLE`, `TRUNCATE`, 无 `WHERE` 的 `DELETE`/`UPDATE`
- 🟡 **需审批**: 影响超过 100 行的写操作、schema 变更
- ✅ **安全**: 所有 `SELECT` 查询、`EXPLAIN ANALYZE`
- 子智能体执行数据库操作前必须加载 `nfmd-db-ops` 技能

## 技术栈

- **数据库**: Supabase (PostgreSQL 16)
- **全文搜索**: PostgreSQL tsvector + 术语表中文转英文
- **前端原型**: 飞书多维表格
- **ETL**: Python 3.14 (`scripts/etl/`)
- **知识库**: llm-wiki 技能体系

## 分支状态

- **main** — 当前活跃分支，包含所有最新代码和数据质量修复
- **phase-2/quality-remediation** — 包含 ETL 测试套件和文档注释，未合并到 main（无冲突但有独立的 docstring 改进）

## License

MIT
