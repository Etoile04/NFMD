# NFMD — Nuclear Fuel Material Database

核燃料材料参数知识库：从文献源抽取材料参数、校验归一后入库，供燃料性能程序查询。单一上下文（single-context）仓库。

## Language

### 数据域

**Parameter**:
从文献抽取的一条材料属性值，取值形态由 value_type 描述。
_Avoid_: property（太泛）、数据项

**Material**:
规范化后的标准材料条目（如 UO2）；一切别名最终归一到它。
_Avoid_: substance

**Alias**:
指向某个 Material 的非规范名称（"二氧化铀" → UO2）。
_Avoid_: 同义词表、synonym

**Literature**:
参数的来源出版物元数据；源文件经归一后关联到它。

**value_type**:
Parameter 的取值形态——scalar（单值）、range（min/max 区间）、expression（公式）、list、text。

**confidence**:
参数可信度评级：high / medium / low。

**business key**:
Parameter 的去重键：`(name, material_id, category, value_type, value_scalar, unit)`；schema 层有唯一约束，同名同料同分类同型同值同单位视为同一参数。
_Avoid_: 主键（那是 id）、唯一索引

**literature_id**:
从 source_file 归一出的稳定 slug，指向 Literature 表；一个 source_file 恰好一条 Literature。

### 管线

**Pipeline**:
从源文件到数据库的五阶段流程：extract → validate → transform → normalize → load。

**ExtractedRecord**:
extract 阶段的产物——尚未校验、尚未归一的原始记录形态。

**TransformedRecord**:
transform/normalize 阶段的产物——已归一、可入库的记录形态。

**ValidationIssue**:
validate 阶段对单条记录的判定（code + severity）。severity 三级：fatal（终止整跑）、error（拦截该记录）、warn（放行但记录）。

**load mode**:
load 阶段策略——append-safe（存在即跳过）、replace-run（business key 命中则更新）、dry-run（只产报告不写库）。

**Settings**:
冻结配置快照（`scripts/etl/config.py`）。环境变量只在 `Settings.from_env` 读一次，且只在入口调用；其余代码一律传参接收。
_Avoid_: config 常量、全局配置、import 时读环境

**alias map**:
Alias 的数据载体（`plans/material-alias-map.json`），由 MaterialNormalizer 消费。

**Run**:
一次管线执行的工件集合（报告、拒收清单等）。

### 角色与安全

**nfmd_reader / nfmd_writer**:
数据库 RLS 双角色（`sql/create_roles.sql`）——reader 只读（API 用），writer 可写数据表（ETL 用）。角色口令只经环境/部署提供，永不出现在源码（见 ADR-0003）。

## Decisions

见 `docs/adr/`。
