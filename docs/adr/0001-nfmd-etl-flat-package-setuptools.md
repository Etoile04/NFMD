# nfmd_etl 采用根目录平铺包 + setuptools，最小公开面，console 入口 nfmd-etl

2026-09 架构走查（深化候选 6+3）决定：ETL 十模块从 `scripts/etl/` 迁为根目录平铺包 `nfmd_etl/`，构建后端 setuptools，`__init__` 不做宽导出（调用方走 `nfmd_etl.<module>`，导出面等真实调用方出现再长），命令行入口 `nfmd-etl = nfmd_etl.run_pipeline:main`。理由：消灭 4 处 sys.path/PYTHONPATH hack 与裸名撞车（load/models/rules），让 `pip install -e .` + pytest 成为唯一验证路径。

## Considered Options

- **src/ 布局**：库项目最佳实践，但对本应用仓库过度——没有防误导入的第三方消费者。
- **hatchling**：配置更短，但此规模下 setuptools 的零惊讶更值钱。
- **依赖 lock**：下界 `>=` 已验证版本即可；集成测试变重再升级 uv lock。
