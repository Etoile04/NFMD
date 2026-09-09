# 依赖只接受、不创建（dependencies accepted, not created）

2026-09 架构走查确立：数据库连接、Settings 等外部依赖一律经接口参数传入，模块内部不再自行创建。落地形态：`load_records` 要求显式 `db_url`（后续 seam 深化改为必填 `conn`）；`run_pipeline` 接受可注入的 `settings`（`None` 时仅限 CLI 入口惰性默认）；API 侧经 `Depends` 链注入。

动机：此前依赖在模块内部创建，测试只能 MagicMock 游标并断言 SQL 字符串（行为 bug 照样出货），且环境变量在 import 时被冻结、无法按调用方变化。

## Considered Options

- **服务定位器 / 全局单例**：模块按需自取依赖——否决，依赖隐藏、测试仍需 patch 全局状态。
- **工厂默认值兜底**（`db_url: str = DB_URL` 式默认）：保留最小过渡形态，但默认值在 import 时求值即重新引入冻结问题，已在 Settings 战役中移除；显式传参始终优先。
