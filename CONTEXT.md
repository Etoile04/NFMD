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
指向某个 Material 的非规范名称（"二氧化铀" → UO2），归一依据 alias map。
_Avoid_: 同义词表、synonym

**Literature**:
参数的来源出版物元数据；源文件路径经 `v_source_file_normalized` 视图归一后关联到它。

**value_type**:
Parameter 的取值形态——scalar（单值）、range（min/max 区间）、expression（公式）、list、text。

**confidence**:
参数可信度评级：high / medium / low。

### 管线

**Pipeline**:
五阶段流程：extract → validate → transform → normalize → load，由 run_pipeline 编排。

**ExtractedRecord**:
extract 阶段的产物——尚未校验、尚未归一的原始记录形态。

**TransformedRecord**:
transform/normalize 阶段的产物——已归一、可入库的记录形态。

**Run**:
一次管线执行的工件集合（报告、拒收清单等），落在 runs base 下的独立 run 目录。

### 工程面

**nfmd_etl**:
ETL 管线的 Python 包；五阶段模块的归宿。公开面保持最小，调用方走子模块导入。
_Avoid_: scripts/etl（旧布局名）、etl（裸名，易撞）

**nfmd-etl**:
管线的命令行入口；console_script 与 `python -m nfmd_etl.run_pipeline` 等价。
