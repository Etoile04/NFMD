# 数据库平台详细计划（OBJ2）

**版本**: v1.1  
**日期**: 2026-04-29  
**状态**: 待启动  
**关联 OKR**: OBJ2 数据库平台（KR 2.1 ~ KR 2.4）  
**前置依赖**: Wiki v3.0 Phase 1.5-2.5 已完成 ✅

---

## 一、现状分析

### 已有基础设施

| 资源 | 状态 | 说明 |
|------|------|------|
| 本地 Supabase | ✅ 运行中 | Docker 11 容器，`supabase_db_workspace` healthy |
| 现有表结构 | 🟡 5 张表 | `materials`(9条), `material_properties`(26条), `irradiation_behavior`, `material_composition`, `literature_sources` |
| 现有 schema | 🟡 简单 | 仅支持标量属性，无类型化值/公式/交叉引用 |
| 同步脚本 | 🟡 RDF→SQL | `sync_to_supabase.py` 基于 RDF 本体，不适合新数据格式 |
| 知识库参数 | ✅ 6,750 条 | 162 个 JSON 文件，覆盖 36 个分类 |

### 现有 Supabase 表 vs 知识库参数结构

**现有表（materials-property-system）**：
- 面向 RDF 本体抽取 → 简单的 name-value-unit 模型
- `material_properties.value` = `numeric(15,5)` → 只能存标量
- 无 category/subcategory/value_type/equation/confidence 字段
- 无文献溯源（只有 literature_sources 单独表）

**知识库参数 JSON 结构**（实际 64 个活跃字段）：
- 类型化值：scalar / range / expression / list / text
- 丰富的元数据：material, temperature_K, method, equation, confidence, source_file
- 分类体系：36 个 category，多种 subcategory
- 交叉引用：通过 source_file 关联到 120+ summaries

**结论**：现有表结构需要**大幅扩展**才能承载知识库数据。

---

## 二、目标定义

### KR 拆解（修订版）

| KR | 描述 | 目标 | 原截止 | 新截止 | 调整理由 |
|----|------|------|--------|--------|----------|
| KR 2.1 | 数据标准规范 | 企业标准初稿 | 06-30 | **05-31** | 数据已有，标准可前置 |
| KR 2.2 | Supabase Schema | 多维度 schema + 迁移 | 05-14 | **05-15** | 需先完成标准规范 |
| KR 2.3 | 数据导入 + 查询 API | 6750+ 可查询参数 | 06-15 | **05-31** | Schema 确定后快速导入 |
| KR 2.4 | 前端原型 | 可演示界面 | 06-30 | **06-15** | 依赖 API 就绪 |

### 成功标准

1. **6750 条参数**全部可通过 API 查询
2. 支持**多维度筛选**（材料、分类、温度、置信度、文献来源）
3. 支持**公式检索**（expression 类型参数可全文搜索）
4. **REST API** 可供外部工具调用（JSRT、BISON 等）
5. 简单**前端原型**支持浏览和搜索

---

## 三、技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   前端展示层                          │
│         Supabase Studio / 自定义 Web UI              │
├─────────────────────────────────────────────────────┤
│                   API 层                             │
│    Supabase REST API (PostgREST)                     │
│    + 自定义 RPC 函数（复杂查询）                       │
├─────────────────────────────────────────────────────┤
│                   数据库层 (PostgreSQL)               │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │materials│ │parameters│ │literature│ │equations│ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────┘ │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐              │
│  │categories│ │xrefs     │ │audit_log │              │
│  └─────────┘ └──────────┘ └──────────┘              │
├─────────────────────────────────────────────────────┤
│                   同步层                              │
│  JSON → SQL ETL / 增量同步 / Webhook 触发            │
├─────────────────────────────────────────────────────┤
│                   数据源                              │
│  knowledge_base/parameters/*.json (6750 条)          │
│  knowledge_base/summaries/*.md (120+ 篇)             │
│  knowledge_base/wiki/ / concepts/ / entities/        │
└─────────────────────────────────────────────────────┘
```

### 3.2 Schema 设计（核心表）

#### `materials` — 材料主表（保留+扩展）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | uuid PK | 主键 |
| name | text UNIQUE | 标准名（如 "U-10Mo"） |
| name_zh | text | 中文名 |
| chemical_formula | text | 化学式 |
| material_type | text | FuelMaterial / StructuralMaterial / ... |
| alloy_system | text | 合金体系（U-Mo, U-Zr, U-Pu-Zr, UN, ...） |
| density | numeric(10,4) | g/cm³ |
| melting_point | numeric(10,2) | K |
| structure | text | bcc / γ-phase / α-phase / etc |
| notes | text | 备注 |
| created_at | timestamptz | |
| updated_at | timestamptz | |

#### `parameters` — 参数主表（新建核心表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | text PK | 原始 ID（如 "151846_f3c95453_param_001"） |
| name | text NOT NULL | 参数名 |
| name_zh | text | 中文名 |
| symbol | text | 符号（LaTeX） |
| category | text NOT NULL | 分类（36 种） |
| subcategory | text | 子分类 |
| value_type | text NOT NULL | scalar / range / expression / list / text |
| value_scalar | numeric(20,10) | 标量值 |
| value_min | numeric(20,10) | 范围最小值 |
| value_max | numeric(20,10) | 范围最大值 |
| value_expr | text | 表达式/公式 |
| value_list | jsonb | 离散值列表 |
| value_text | text | 文本描述 |
| value_str | text | 原始字符串表示 |
| unit | text | 单位 |
| uncertainty | text | 不确定度 |
| material_id | uuid FK | 关联材料 |
| material_raw | text | 原始材料字符串 |
| temperature_k | numeric(10,2) | 温度条件 (K) |
| temperature_str | text | 温度原始字符串 |
| method | text | 测量/计算方法 |
| confidence | text | high / medium / low |
| source_file | text | 来源 summary 文件 |
| equation | text | 关联公式 |
| notes | text | 备注 |
| ts_vector | tsvector | 全文搜索向量 |
| created_at | timestamptz | |

**索引**：
- `idx_params_category` ON (category)
- `idx_params_material` ON (material_id)
- `idx_params_value_type` ON (value_type)
- `idx_params_confidence` ON (confidence)
- `idx_params_source` ON (source_file)
- `idx_params_search` ON (ts_vector) — GIN 索引，全文搜索
- `idx_params_symbol` ON (symbol)
- `idx_params_material_raw` ON (material_raw)

#### `literature` — 文献表（替换 literature_sources）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | text PK | slug（如 "Kim_2013_xxx"） |
| title | text | 标题 |
| authors | text | 作者列表 |
| journal | text | 期刊 |
| year | integer | 年份 |
| doi | text | DOI |
| file_path | text | Zotero 本地路径 |
| parameter_count | integer | 关联参数数 |
| created_at | timestamptz | |

#### `categories` — 参数分类字典表

| 列名 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| name | text UNIQUE | 分类名 |
| name_zh | text | 中文名 |
| description | text | 描述 |
| parent | text | 父分类（层级） |
| param_count | integer | 参数数 |

#### `equations` — 公式表（可选，Phase 2）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| latex | text | LaTeX 公式 |
| description | text | 公式说明 |
| source_file | text | 来源 |
| parameter_ids | text[] | 关联参数 |

#### `cross_references` — 交叉引用表（可选，Phase 2）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| from_id | text FK | 源参数 |
| to_type | text | summary / concept / entity |
| to_id | text | 目标 ID |
| relation | text | 引用类型 |

#### `audit_log` — 审计表

| 列名 | 类型 | 说明 |
|------|------|------|
| id | serial PK | |
| action | text | INSERT / UPDATE / DELETE |
| table_name | text | 表名 |
| record_id | text | 记录 ID |
| changes | jsonb | 变更内容 |
| operator | text | 操作者 |
| timestamp | timestamptz | |

### 3.3 材料名规范化映射

知识库中存在大量异名（如 "U-10Mo", "U-10wt.%Mo", "U-10 wt% Mo" 都是同一材料），需要建立映射表：

```python
# material_aliases 表 或 映射字典
MATERIAL_ALIASES = {
    "U-10Mo": "U-10Mo",
    "U-10wt.%Mo": "U-10Mo",
    "U-10 wt% Mo": "U-10Mo",
    "U-10 wt.%Mo": "U-10Mo",
    "U-Mo": "U-Mo (generic)",
    "U-7Mo (bcc)": "U-7Mo",
    "U-Pu-Zr": "U-Pu-Zr (generic)",
    "U-Zr": "U-Zr (generic)",
    "U-10Zr": "U-10Zr",
    "U-19Pu-10Zr": "U-19Pu-10Zr",
    "U-Pu-10Zr": "U-Pu-10Zr",
    "α-U": "α-U",
    # ... 需要从数据中提取完整列表
}
```

---

## 四、分阶段执行计划

### Phase 1: Schema 设计 + 数据标准（05-01 ~ 05-07）

**目标**：完成表结构设计、数据标准文档、材料规范化映射

| 任务 | 工时 | 交付物 |
|------|------|--------|
| 1.1 材料名规范化 | 2h | 映射字典 + materials 表种子数据 |
| 1.2 Schema DDL 编写 | 3h | SQL migration 文件 |
| 1.3 数据标准文档 | 2h | Markdown 文档（字段定义、约束规则、命名约定） |
| 1.4 全文搜索配置 | 1h | tsvector 触发器 + 中英文分词 |
| 1.5 测试数据导入验证 | 1h | 100 条样本参数导入测试 |

**关键决策**：
- 现有 5 张表是否保留？→ 建议**保留** `materials` 并扩展，其余 4 张**重建**
- 新建独立 schema（`fuel_kb`）还是复用 `public`？→ 建议 `public`，简化访问
- 是否需要版本控制（参数变更历史）？→ Phase 1 先不做，Phase 2 加 `audit_log`

### Phase 2: ETL + 数据导入（05-08 ~ 05-15）

**目标**：6750 条参数全部导入 Supabase

| 任务 | 工时 | 交付物 |
|------|------|--------|
| 2.1 ETL 脚本编写 | 4h | `etl_parameters.py`（JSON → SQL） |
| 2.2 材料自动识别 | 2h | material_raw → material_id 映射逻辑 |
| 2.3 全量导入 | 2h | 162 个文件 → 6750 条参数 |
| 2.4 数据校验 | 2h | 导入后完整性检查（计数、null 检查、FK 验证） |
| 2.5 文献关联 | 2h | 从 source_file 提取文献元数据填充 literature 表 |
| 2.6 增量同步机制 | 2h | 监控 JSON 文件变更 → 触发增量更新 |

**ETL 核心逻辑**：
```python
# 伪代码
for json_file in parameters/*.json:
    params = json.load(json_file)
    for p in params:
        # 1. 材料规范化
        material_id = resolve_material(p['material_raw'])
        
        # 2. 类型化值映射
        if p['value_type'] == 'scalar':
            value_scalar = p['value']
        elif p['value_type'] == 'range':
            value_min, value_max = p['value_min'], p['value_max']
        elif p['value_type'] == 'expression':
            value_expr = p['value_expr'] or p.get('equation', '')
        # ...
        
        # 3. 全文搜索向量
        ts_vector = to_tsvector(f"{p['name']} {p.get('name_zh','')} {p.get('symbol','')}")
        
        # 4. UPSERT
        upsert_parameter(p['id'], ...)
```

### Phase 3: API + 查询优化（05-16 ~ 05-25）

**目标**：REST API 可用，支持多维度查询

| 任务 | 工时 | 交付物 |
|------|------|--------|
| 3.1 Supabase View 定义 | 2h | 常用查询视图（按材料/分类聚合） |
| 3.2 RPC 函数 | 3h | 复杂查询（跨表搜索、范围筛选、排序） |
| 3.3 API 文档 | 1h | OpenAPI spec / Markdown |
| 3.4 性能测试 | 1h | 6750 条数据的查询响应时间 |
| 3.5 RLS 策略 | 1h | 行级安全（公开读取、认证写入） |

**核心 API 端点**（Supabase PostgREST 自动生成 + 自定义 RPC）：

```
GET /rest/v1/parameters?category=eq.diffusion&material_id=eq.xxx
GET /rest/v1/parameters?id=eq.151846_f3c95453_param_001
GET /rest/v1/categories?select=name,param_count
POST /rest/v1/rpc/search_parameters  { "query": "diffusion U-10Mo", "limit": 50 }
POST /rest/v1/rpc/params_by_material { "material": "U-10Mo", "category": "diffusion" }
POST /rest/v1/rpc/stats_overview     {}
```

### Phase 4: 前端原型 + 集成（05-26 ~ 06-15）

**目标**：可演示的前端界面

| 任务 | 工时 | 交付物 |
|------|------|--------|
| 4.1 技术选型 | 1h | 方案 A: Supabase Studio 扩展 / 方案 B: 独立前端 |
| 4.2 材料浏览器 | 3h | 材料列表 → 参数列表 → 参数详情 |
| 4.3 搜索界面 | 3h | 全文搜索 + 分类/材料筛选 |
| 4.4 参数对比 | 2h | 多来源同一参数对比视图 |
| 4.5 Zotero 集成 | 2h | 文献详情 → Zotero 链接 |
| 4.6 部署 | 1h | 本地 Docker / 或 Supabase Cloud |

**前端方案对比**：

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| A. Supabase Studio | 零开发、开箱即用 | 功能固定、无法定制 | 快速验证 |
| B. React + Supabase JS | 完全定制 | 开发量大 | 正式产品 |
| C. Streamlit | 快速原型、Python 生态 | 性能一般 | 科研演示 |
| **D. 飞书多维表格** | **零前端开发** | 灵活性有限 | **推荐首选** |

**推荐路径**：先用**飞书多维表格**做可交互原型（Agent 直接操作），同时保留 Supabase 作为正式数据后端。

### Phase 5: 自动化 + 运维（06-16 ~ 06-30）

**目标**：自动化 pipeline，减少手工操作

| 任务 | 工时 | 交付物 |
|------|------|--------|
| 5.1 增量同步 cron | 2h | 定时检查 JSON 变更 → 自动同步 |
| 5.2 数据质量监控 | 2h | null 率、FK 完整性、重复检查 |
| 5.3 备份策略 | 1h | pg_dump 定时备份 |
| 5.4 共享机制 | 2h | 导出 CSV/JSON / API token 分发 |
| 5.5 文档完善 | 2h | 用户手册 + 开发者文档 |

---

## 五、关键技术决策

### 5.1 本地 Supabase vs Supabase Cloud

| 维度 | 本地 Docker | Supabase Cloud |
|------|-------------|----------------|
| 数据安全 | ✅ 完全本地 | ⚠️ 云端存储 |
| 成本 | ✅ 免费 | ⚠️ Free tier 500MB |
| 协作 | ❌ 需额外配置 | ✅ 开箱即用 |
| 性能 | ✅ 低延迟 | ⚠️ 网络延迟 |
| 维护 | ⚠️ 需自行运维 | ✅ 托管 |

**决策**：先本地 Docker 开发测试，后续上 Supabase Cloud 方便团队共享。

### 5.2 参数值存储策略

**方案 A：单表 + 类型化列**（推荐）
```sql
CREATE TABLE parameters (
    value_type text NOT NULL,
    value_scalar numeric(20,10),  -- null if not scalar
    value_min numeric(20,10),     -- null if not range
    value_max numeric(20,10),
    value_expr text,              -- null if not expression
    value_list jsonb,             -- null if not list
    ...
);
```

**方案 B：JSONB 存储**
```sql
CREATE TABLE parameters (
    value jsonb NOT NULL,  -- {"type":"scalar","value":5.0}
    ...
);
```

**选择 A**：
- 类型化列查询性能更好（原生索引）
- SQL 约束可直接校验
- 但需要 ETL 层做类型映射

### 5.3 全文搜索方案

PostgreSQL `tsvector` + 自定义字典：
- 英文：默认 `english` 配置
- 中文：需 `pg_jieba` 或 `zhparser` 扩展（Docker 镜像需重新构建）
- **Phase 1 先用英文 tsvector**，Phase 2 加中文支持

### 5.4 与 Zotero 集成方案

| 方案 | 实现方式 | 优先级 |
|------|----------|--------|
| 文献元数据同步 | Zotero MCP → literature 表 | Phase 2 |
| PDF 路径关联 | source_file → Zotero storage 路径 | Phase 2 |
| 参数→文献反向链接 | parameters.source_file → literature | Phase 3 |

---

## 六、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 材料名规范化遗漏 | 高 | 查询不完整 | 从数据自动生成映射表 + 人工审核 |
| Docker 磁盘不足 | 中 | 服务中断 | 定期清理 WAL、限制日志 |
| 全文搜索中文分词差 | 中 | 中文搜索不准 | Phase 1 先英文，Phase 2 加 pg_jieba |
| API 性能不足 | 低 | 查询慢 | 合理索引 + 物化视图 |
| 数据不一致 | 中 | 查询错误 | ETL 校验 + audit_log |

---

## 七、里程碑与验收

| 里程碑 | 日期 | 验收标准 |
|--------|------|----------|
| **M2.1 Schema 确认** | 05-07 | DDL 执行成功，测试数据导入 100 条无错 |
| **M2.2 全量导入** | 05-15 | 6750 条参数全部入库，FK 完整性 100% |
| **M2.3 API 就绪** | 05-25 | REST API 查询可用，平均响应 < 100ms |
| **M2.4 前端原型** | 06-15 | 飞书多维表格可浏览 + 搜索参数 |
| **M2.5 自动化** | 06-30 | 增量同步 cron 运行，备份正常 |

---

## 八、资源需求

| 资源 | 说明 |
|------|------|
| 开发时间 | ~60 工时（5 月 ~ 6 月） |
| 磁盘 | 当前 Docker 693MB，预计增长到 1-2GB |
| 外部依赖 | Supabase Docker, PostgreSQL, Python 3.14 |
| 人工审核 | 材料名映射审核（~1h）、数据抽检（~2h） |

---

*下一步：确认此计划后，从 Phase 1（Schema 设计）开始执行。需要你确认的关键决策已在第五节标出。*
