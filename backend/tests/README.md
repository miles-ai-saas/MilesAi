# 后端测试目录

与 [packages/](../packages/) 的包边界对齐：**一级目录 = 被测包**，深层 = 该包内的模块目录；
用例文件的位置 ⇔ 被测模块的位置（`miles_runner` 当前无直接用例，能力经 `miles_exec` 覆盖，故无对应目录）。
归属规则与逐文件映射见
[docs/superpowers/specs/2026-09-21-tests-structure-design.md](../../docs/superpowers/specs/2026-09-21-tests-structure-design.md)。

```text
tests/
  conftest.py          # 全局 fixture（api_app、api_client 等）
  paths.py             # 路径常量（勿在子目录内猜 backend 根，用 TESTS_ROOT/BACKEND_ROOT/PACKAGES）
  test_l3_neutral_imports.py          # AST 守卫：L3 反向依赖 / server 自建 router
  test_no_blocking_calls_in_async.py  # AST 守卫：async 内不得直调阻塞调用
  test_no_silent_broad_except.py      # AST 守卫：宽泛 except / suppress 不得静默（日志须带 exc_info）
  test_no_unreferenced_modules.py     # AST 守卫：不得出现零引用模块（入口点白名单除外）
  test_domain_meta.py                 # 各租户域 /meta 契约聚合
  test_api_enum_parity.py             # API 枚举声明与 ORM 逐字节一致
  test_enum_contract.py               # StrEnum 迁移契约
  test_orm_registry_completeness.py   # 全仓 ORM 表登记可达
  test_tests_layout.py                # 结构守卫：一级目录白名单 / 包前缀自洽 / 基名唯一
  integration/                        # 跨包编排（≥2 个包协作）
  miles_common/ miles_exec/ miles_core/ miles_ai/
  miles_portal/ miles_admin/ miles_openapi/ miles_server/ miles_worker/
```

跑测试（必须在 `backend/` 下用 `python -m pytest`：`tests.paths` / `tests.conftest`
依赖 `backend/` 在 `sys.path`）：

```bash
python -m pytest -q                        # 全量
python -m pytest -q tests/miles_ai/rag     # 单包单模块
python -m pytest -q tests/miles_server/apps/test_api_e2e.py
```
