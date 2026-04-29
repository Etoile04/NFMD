# Phase 2 ETL + 全量导入设计

## 概述

本设计定义 NFMD 的 Phase 2 ETL 管线，用于将知识库中 162 个 JSON 文件、约 6750 条参数记录高质量导入 Supabase PostgreSQL。目标不是“尽快写进去”，而是建立一套 **质量优先、可重跑、可审计、可扩展** 的导入流程，为后续增量同步和 API 层复用打基础。

本阶段采用 **分阶段 ETL Pipeline**，而不是单脚本直写数据库，也暂不引入完整 staging schema。坏数据不进入正式 `parameters` 表，但必须被完整记录并可追踪。

## 目标

1. 从 `data/fuel_swelling_wiki/parameters/*.json` 提取参数记录并统一建模。
2. 在导入前执行分级校验，优先保证数据质量。
3. 将材料、文献、单位、温度、值类型等字段规范化。
4. 将通过校验的数据批量写入 Supabase。
5. 对每次导入产出完整的 issues、summary、run metadata，支持审计和重跑。

## 非目标

本阶段不包含：

- Web UI 或飞书前端实现
- 定时 cron 增量同步
- 复杂 staging 数据库设计
- 高级全文搜索优化（超出当前 schema + terminology 支持）
- 自动“智能修复”所有脏数据

## 总体架构

ETL 分为四个独立阶段：

1. **extract**：读取源 JSON 并生成统一中间记录。
2. **validate**：执行规则校验并给出分级结果。
3. **transform**：完成归一化、字段拆解、映射与标准化。
4. **load**：批量写入数据库并生成导入统计。

每个阶段都必须落盘并可独立重跑，不依赖长链路内存态。

## 目录结构

```text
NFMD/
  scripts/etl/
    run_pipeline.py
    extract.py
    validate.py
    transform.py
    load.py
    models.py
    rules.py
    normalize.py
    io_utils.py
  data/
    imports/
      runs/<run_id>/
        run-meta.json
        01-extracted.jsonl
        02-validated.jsonl
        02-issues.jsonl
        03-transformed.jsonl
        04-load-summary.json
```

## 阶段设计

### 1. extract

职责：

- 扫描 `data/fuel_swelling_wiki/parameters/*.json`
- 读取所有参数记录
- 将不同来源统一为中间模型
- 保留所有原始事实字段，不做业务修复

输出：`01-extracted.jsonl`

extract 只做结构统一，不做值修正，不做材料映射，不做单位转换。

### 2. validate

职责：

- 根据规则检查记录完整性、合法性和可导入性
- 为每条记录打上 `fatal / error / warn` 级别问题
- 决定记录是否允许进入 transform / load

输出：

- `02-validated.jsonl`
- `02-issues.jsonl`

validate 只负责判断和标记，不负责修数据。所有修正规则归 transform 管理。

### 3. transform

职责：

- 材料名归一化
- 文献主键归一化
- 值类型拆解到 schema v2 对应字段
- 单位标准化
- 温度解析
- 生成接近数据库写入结构的标准记录

输出：`03-transformed.jsonl`

### 4. load

职责：

- 批量 upsert `literature`
- 校验和使用现有 `materials` / `material_aliases`
- 必要时同步 `categories`
- 批量 insert / upsert `parameters`
- 生成最终导入统计和异常摘要

输出：`04-load-summary.json`

## 校验分级

### fatal

fatal 表示输入或运行环境本身存在系统性问题，本次导入必须立即终止。

示例：

- 输入文件缺失或无法解析
- JSON 总体结构不符合预期
- 数据库连接失败
- schema 与 ETL 映射定义不一致
- `material-alias-map.json` 无法加载
- alias 冲突导致材料映射表不可用

处理策略：中止整批 run，输出失败原因。

### error

error 表示单条记录不可进入正式表，但不应拖死整批导入。

示例：

- `value_type` 无法识别
- `scalar` 缺 `value_scalar`
- `range` 缺上下界
- 文献主键无法稳定生成
- 材料无法映射到标准材料
- category 不在允许集合中
- 参数主键冲突且无法判定保留哪条

处理策略：

- 记录写入 `02-issues.jsonl`
- 该记录不进入 `03-transformed.jsonl`
- 继续处理其他记录

### warn

warn 表示记录可入库，但质量不完美，后续需要清洗。

示例：

- `confidence` 缺失
- `name_en` 缺失但 `name` 存在
- 单位格式不统一但可标准化
- 材料映射成功但原始字符串较脏
- 文献元信息不完整

处理策略：

- 允许进入 transform / load
- 问题写入 `02-issues.jsonl`
- 在 summary 中单独统计 warning

## Issues 输出格式

每个 issue 一条 JSONL，结构如下：

```json
{
  "run_id": "2026-04-29T20-00-00",
  "severity": "error",
  "stage": "validate",
  "source_file": "Beeler_2020.summary.json",
  "record_id": "151846_f3c95453_param_001",
  "code": "UNKNOWN_MATERIAL",
  "message": "material_raw='U-Mo/Al弥散板' not mapped to canonical material",
  "context": {
    "material_raw": "U-Mo/Al弥散板",
    "name": "swelling rate"
  }
}
```

## 中间数据模型

extract 输出使用统一中间模型，优先贴近原始事实而不是数据库字段：

```json
{
  "record_id": "...",
  "source_file": "...",
  "paper_id": "...",
  "paper_title": "...",
  "name": "...",
  "name_zh": "...",
  "name_en": "...",
  "symbol": "...",
  "category": "...",
  "subcategory": "...",
  "value_type": "scalar|range|expression|list|text",
  "raw_value": "...",
  "raw_unit": "...",
  "raw_material": "...",
  "raw_temperature": "...",
  "raw_burnup": "...",
  "raw_method": "...",
  "raw_confidence": "...",
  "notes": "...",
  "equation": "..."
}
```

### 设计原则

- `raw_*` 字段保留原始提取事实
- transform 生成 normalized 字段
- 中间模型允许比数据库结构更冗余，但必须便于追溯

## Transform 规则

### 材料归一化

- 使用 `plans/material-alias-map.json`
- `raw_material` 成功映射后生成 `material_name`
- `load` 阶段再查 `material_id`
- 无法映射时记为 `error`

### 参数值拆解

- `scalar` → `value_scalar`
- `range` → `value_min`, `value_max`
- `expression` → `value_expr`
- `list` → `value_list`
- `text` → `value_text`

始终保留 `value_str` 作为原始字符串表示。

### 单位标准化

仅使用有限、显式的标准化字典，不做过度智能推断。

示例：

- `m2/s` → `m²/s`
- `W/mK` → `W/(m·K)`

### 温度解析

- 能解析则写 `temperature_k`
- 原文始终保留在 `temperature_str`

示例：

- `600 K` → `temperature_k = 600`
- `350 °C` → `temperature_k = 623.15`
- `room temperature` → `temperature_k = null`, `temperature_str = "room temperature"`

### 文献归一化

为每条参数生成稳定的文献主键，优先级如下：

1. DOI
2. Zotero key / 内部 paper key
3. `Author_Year_TitleSlug`

## Transformed 输出模型

`03-transformed.jsonl` 的记录应接近数据库写入模型，例如：

```json
{
  "id": "151846_f3c95453_param_001",
  "name": "扩散系数",
  "name_zh": "扩散系数",
  "name_en": "diffusion coefficient",
  "symbol": "D_v",
  "category": "diffusion",
  "subcategory": "diffusion_parameter",
  "value_type": "scalar",
  "value_scalar": 1.5e-12,
  "value_min": null,
  "value_max": null,
  "value_expr": null,
  "value_list": null,
  "value_text": null,
  "value_str": "1.5×10^-12",
  "unit": "m²/s",
  "material_name": "U-10Mo",
  "material_raw": "U-10Mo",
  "temperature_k": 623.15,
  "temperature_str": "350 °C",
  "confidence": "high",
  "source_file": "Beeler_2020.summary.json"
}
```

## Load 策略

### 写入顺序

固定写入顺序：

1. `literature`
2. `materials` / `material_aliases`
3. `categories`（如需同步）
4. `parameters`

### 幂等性

#### literature

- 使用稳定主键 upsert
- 允许补充缺失字段
- 不允许用更差的数据覆盖更完整的数据

#### parameters

- 使用 `id` 作为唯一幂等键
- 支持重跑时 upsert
- 若关键字段变化（如 `value_type`, `material_raw`, `category`），必须在 summary 中可见
- 禁止静默覆盖造成数据漂移

## 运行模式

### dry-run

执行 extract / validate / transform / summary，不写数据库。

用途：全量质量检查和规则调试。

### append-safe

只写入数据库中不存在的记录。若同 ID 已存在，则跳过并记入 summary。

用途：安全补录。

### replace-run

允许对当前输入集合执行 upsert 更新。必须显式传参启用，避免误覆盖。

用途：规则修正后重跑整批或子集。

## 批量写入策略

- 参数写入按 500~1000 条分 batch
- 使用 PostgreSQL 批量 insert / upsert
- 默认不逐条写入
- 若某批失败，可降级定位到单条坏记录

## 导入结果报告

每次 run 结束必须生成 `04-load-summary.json`，至少包含：

```json
{
  "run_id": "...",
  "mode": "dry-run",
  "source_files": 162,
  "records_extracted": 6750,
  "records_valid": 6421,
  "records_warn": 211,
  "records_error": 118,
  "records_fatal": 0,
  "literature_inserted": 23,
  "literature_updated": 81,
  "parameters_inserted": 6400,
  "parameters_updated": 21,
  "parameters_skipped": 0
}
```

summary 还应补充：

- top 10 error codes
- 未映射材料清单

## Run Metadata

每次运行必须生成 `run-meta.json`，记录：

- 输入路径
- run_id
- git commit
- schema version
- material alias map version
- mode
- started_at
- finished_at

## 脚本边界

建议脚本边界如下：

- `run_pipeline.py`：CLI 入口，串联全流程
- `extract.py`：文件读取与中间记录生成
- `validate.py`：规则执行与 issue 输出
- `transform.py`：归一化和字段映射
- `load.py`：数据库写入
- `models.py`：数据模型
- `rules.py`：规则枚举与注册
- `normalize.py`：单位、温度、材料名辅助逻辑
- `io_utils.py`：JSONL / run 目录读写工具

## CLI 设计

主入口：

```bash
python scripts/etl/run_pipeline.py --mode dry-run
python scripts/etl/run_pipeline.py --mode append-safe
python scripts/etl/run_pipeline.py --mode replace-run
```

可选调试入口：

```bash
python scripts/etl/extract.py --run-id ...
python scripts/etl/validate.py --run-id ...
python scripts/etl/transform.py --run-id ...
python scripts/etl/load.py --run-id ...
```

默认场景只使用主入口，分阶段入口用于调试和局部重跑。

## 测试策略

### 单元测试

重点覆盖纯函数：

- value_type 拆解
- 温度解析
- 单位标准化
- 材料别名映射
- 文献 ID 生成

### 小样本集成测试

准备 10~20 条覆盖多种情况的 fixture，覆盖：

- scalar / range / expression / list / text
- 映射成功 / 映射失败
- warning / error / fatal
- 文献去重
- 参数 upsert

### 全量 dry-run 验证

正式写库前，必须先跑：

```bash
python scripts/etl/run_pipeline.py --mode dry-run
```

通过标准：

- fatal = 0
- error 数量可解释
- warning 有完整统计和清单
- summary / issues 文件完整

### 实库 smoke test

正式全量 load 前，先用小样本写空库验证：

- FK 正常
- CHECK 正常
- 审计触发器正常
- 中文搜索 RPC 不被导入数据破坏

## Phase 2 MVP 交付范围

本阶段最小可交付闭环包括：

1. 统一中间模型
2. 4 阶段 ETL 可运行
3. `dry-run / append-safe / replace-run` 三种模式
4. issue 分级输出
5. load summary 输出
6. 6750 条参数全量导入成功
7. 导入后基础 SQL 验证脚本

## 关键决策

1. 选择分阶段 Pipeline，而不是单脚本串行 ETL。
2. 选择质量优先，而不是一次性全量导入优先。
3. 选择分级失败处理：fatal 中止、error 隔离、warn 留痕放行。
4. 选择文件级中间产物，而不是一开始引入完整 staging schema。
5. 选择以 `id` 为参数幂等键，支持重跑但禁止静默覆盖。

## 风险与应对

### 风险 1：材料映射覆盖仍不足

应对：

- dry-run 输出未映射材料清单
- 将 alias map 更新作为导入前置修复循环的一部分

### 风险 2：单位和温度解析规则不稳定

应对：

- 仅支持显式规则集
- 无法确定时保留原始字符串，不做猜测性转换

### 风险 3：批量写入时局部坏记录难定位

应对：

- 先分 batch
- batch 失败时降级到更小粒度重试定位

### 风险 4：replace-run 误覆盖

应对：

- 必须显式启用 replace-run
- summary 输出 updated 计数和关键字段变化统计

## 成功标准

当以下条件满足时，Phase 2 视为完成：

1. dry-run 在全量 6750 条数据上 `fatal = 0`
2. error 记录被完整隔离并形成清单
3. transformed 记录可无约束错误写入 schema v2
4. full load 成功完成并生成 summary
5. 导入后数据库查询、触发器、RPC 基础 smoke test 通过
6. 全流程可在相同输入上安全重跑
