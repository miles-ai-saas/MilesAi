# tests 目录按 packages 镜像重构设计

日期：2026-09-21
范围：`backend/tests/`（209 个 `test_*.py`，迁移前 `pytest --collect-only` = 1513 个用例）
非范围：`packages/` 源码、`.importlinter` 分层契约、`pyproject.toml` 的 `testpaths`

## 1. 背景：测试目录与包结构已经错位

`backend/packages/` 是 10 个 uv workspace 包，每个包的源码在 `<pkg>/src/<module>/`：

```text
miles-common   → miles_common    # idgen、cron、schema、redis_keys
miles-exec     → miles_exec      # mcp 协议内核、sandbox
miles-core     → miles_core      # infra、models、web、risk、jobs、utils
miles-ai       → miles_ai        # rag、flow_runtime、integrations
miles-portal   → miles_portal    # tenant/*、marketplace、deletion
miles-admin    → miles_admin     # app_ops、app_sys、models
miles-openapi  → miles_openapi   # views
miles-server   → miles_server    # apps、scripts、cli
miles-worker   → miles_worker    # app、tasks
miles-runner   → miles_runner    # 沙箱 HTTP 服务
```

`backend/tests/` 仍按「域」分目录（`api/ flow/ rag/ media/ mcp/ infra/ models/ tenant/ …`），
这套划分来自单包时代的 `backend/app/`，与现在的包边界不再对应：

| 现状目录 | 实际横跨的包 |
|---|---|
| `tests/flow/` (24) | `miles_ai`（flow_runtime、integrations.langgraph）20 + `miles_portal`（tenant/flows）4 |
| `tests/rag/` (22) | `miles_ai`（rag、integrations.embeddings/rerank/langgraph）17 + `miles_portal`（tenant/kb、deletion）5 |
| `tests/infra/` (26) | `miles_core` 14 + `miles_ai` 4 + `miles_portal` 3 + `miles_server` 2 + `miles_worker` 2 + `miles_common` 1 |
| `tests/api/` (12) | `miles_server` 5 + `miles_portal` 3 + `miles_openapi` 1 + `miles_core` 1 + 跨包 2 |
| `tests/mcp/` (6) | `miles_exec` 2 + `miles_portal` 2 + `miles_ai` 1 + `miles_server` 1 |
| `tests/media/` (7) | `miles_ai`（integrations.generative）5 + `miles_portal`（tenant/media_assets）2 |
| `tests/tenant/tools/` (18) | `miles_portal` 10 + `miles_ai`（integrations.langchain）4 + `miles_exec`（sandbox）3 + `miles_core` 1 |
| `tests/tenant/agents/` (25) | `miles_portal`（tenant/agents）19 + `miles_portal`（tenant/a2a）5 + `miles_ai`（integrations.deepagents）1 |

`miles_common`、`miles_exec`、`miles_runner`、`miles_server`、`miles_worker` 在测试侧根本没有对应目录：
它们的用例散落在 `tests/infra/`、`tests/mcp/`、`tests/worker/`、`tests/tenant/tools/` 里。

后果有三条，都是这次要修的：

1. 「某个模块的用例在哪」答不出，只能全仓 grep import；
2. 包边界在测试侧不可见，`.importlinter` 的 6 条契约在测试目录上没有投影；
3. 域内文件被误认为同类：`tests/tenant/tools/test_script_exec.py` 测的是 `miles_exec.sandbox`，
   与同目录的 `test_tools_invoke.py` 分属两个包，改动 `miles_exec` 时的受影响范围难以判断。

## 2. 目标与归属规则

**目标**：`tests/` 的一级目录 = 被测包（`miles_core`、`miles_ai`、`miles_portal` …），
二级及以下 = 该包内的模块目录；**用例文件的位置 ⇔ 被测模块的位置**，看目录即可定位被测代码。

归属规则按优先级：

| # | 规则 | 判例 |
|---|---|---|
| R1 | 有单一被测模块 → 落到该模块 import 路径对应的目录 | `miles_portal.tenant.agents.services.agent` → `tests/miles_portal/tenant/agents/` |
| R2 | 被测对象是**应用装配 / 壳层**（`create_app`、`miles_server.main`、CORS、异常处理器、health、访问日志、整链 E2E）→ `tests/miles_server/` | `api/test_api_e2e.py` 断言的是装配后的整链，不落到 `tenant/flows/` |
| R3 | 被测对象是**跨包契约**（≥2 个包、无单一被测模块）→ 根级守卫或 `tests/integration/` | `test_l3_neutral_imports.py` 扫 10 个包；`integration/test_integration_pipeline.py` 串 `miles_ai` + `miles_portal` |

R1 优先于 R2/R3；R2、R3 只在「没有单一被测模块」时生效。没有兜底目录：跨域文件按被测对象归到具体域，
确实无单一归属的按 R3 处理。

**非目标**（本次明确不做）：

- 不改用例逻辑、断言、fixture、mock 目标字符串；
- 不重命名测试文件（唯一例外见 §4.2 的 `test_p1_features.py`）；
- 不拆 `tests/tenant/skills/`、`tests/miles_portal/tenant/agents/` 这类已经同域的目录；
- 不动 `.importlinter`；不改 `pyproject.toml` 的 `testpaths = ["tests"]`；
- 不新增/删除用例（迁移前后用例集合必须逐条一致）。

## 3. 目标目录树

```text
backend/tests/
├── conftest.py                        # 全局 fixture（留根，子目录用 tests.conftest 引用）
├── paths.py                           # 路径常量（新增 TESTS_ROOT，见 §4.3）
├── test_l3_neutral_imports.py         ┐
├── test_no_blocking_calls_in_async.py │ 跨包 AST 守卫（R3），留根
├── test_no_silent_broad_except.py     │
├── test_no_unreferenced_modules.py    ┘
├── test_domain_meta.py                # 18 个租户域的 /meta 契约聚合（R3）
├── test_api_enum_parity.py            # API 枚举声明 vs ORM 逐字节一致（R3）
├── test_enum_contract.py              # StrEnum 迁移契约（跨 core + portal，R3）
├── test_orm_registry_completeness.py  # 全仓 ORM 表登记可达（R3）
├── test_tests_layout.py               # 本次新增：测试目录结构守卫（§4.4）
├── integration/                       # 跨包编排（R3）
├── miles_common/
├── miles_exec/{mcp,sandbox}/
├── miles_core/{infra/{db,vector_store},models,utils,web}/ + 包根单模块
├── miles_ai/{rag,flow_runtime,integrations/{langchain,langgraph,generative,embeddings,rerank,litellm,deepagents}}/
├── miles_portal/{tenant/{a2a,agents,attachments,compliance,flows,generative,hooks,kb,
│                          marketplace,mcp/runner,media_assets,models,prompts,skills,
│                          system,tools},marketplace,deletion}/
├── miles_admin/{app_ops,app_sys,models}/
├── miles_openapi/views/
├── miles_server/{apps,scripts/seed}/
└── miles_worker/{tasks}/
```

`integrations/` 下一律只到子包一层（`integrations/langchain/`，不再细分 `toolkit/`、`tool_agent/`），
与「镜像到包内模块层」的粒度一致；`tenant/mcp/runner/` 是既有子目录，原样保留。

`miles_runner`（沙箱 HTTP 服务）当前没有直接用例，其能力经 `tests/miles_exec/mcp/` 覆盖，
故目标树中不建该目录，但 §4.4 的白名单保留它（新增用例时无需改守卫）。

## 4. 迁移机制

### 4.1 分批 `git mv`

纯路径搬迁，5 批各自独立可验证（表内为搬迁的文件数；根级 4 个 AST 守卫与
`integration/test_integration_pipeline.py` 原地不动）：

| 批 | 内容 | 文件数 |
|---|---|---|
| 1 | `miles_common`、`miles_exec`、`miles_worker`、`miles_server`、`miles_openapi`（含 `infra/`、`mcp/`、`tenant/tools/` 里的散件） | 19 |
| 2 | `miles_core`（`infra/{db,vector_store}`、`models/`、`web/`、`utils/` + 包根单模块） | 19 |
| 3 | `miles_ai`（`rag/`、`flow_runtime/`、`integrations/*`） | 57 |
| 4 | `miles_portal`（`tenant/*`、`marketplace/`、`deletion/`） | 98 |
| 5 | `miles_admin/` 5 + 守卫上移到根 4 + `test_module_smoke` 移入 `integration/` 1 + 文档 + 新增结构守卫 | 10 |

合计搬迁 203 个文件，驻留原位 5 个，源文件总数 209（其中 `test_p1_features.py` 按 §4.2 拆为 2 个文件）。
每批：`git mv` → 跑该批目标目录 `pytest -q` → 提交。第 5 批后跑全量。

### 4.2 唯一的文件拆分

`tests/api/test_p1_features.py`（两个域的 schema 冒烟）按被测对象拆为两个文件，避免「一个文件两个包」：

- `tests/miles_portal/tenant/tasks/test_task_batch_cancel.py`（`TaskBatchCancelBody` 用例）
- `tests/miles_portal/tenant/generative/test_generative_batch_cancel.py`（`GenerativeJobBatchCancelBody` 用例）

拆后两侧基名不同（同基名会在无 `__init__.py` 的 pytest `prepend` 模式下触发 import mismatch）。

### 4.3 消灭 `parents[N]` 硬编码

目录深度由 1–2 层变为 2–4 层后，4 处 `Path(__file__).resolve().parents[2]` 会静默指错：

| 文件 | 现状 | 迁移后 |
|---|---|---|
| `tests/infra/test_canvas_state_contract.py` | `parents[2]` | `from tests.paths import BACKEND_ROOT` |
| `tests/infra/test_loop_aware_engine.py` | `parents[2]` | 同上 |
| `tests/infra/test_run_worker_db_coro.py` | `parents[2] / "packages/…"` | `from tests.paths import PACKAGES` |
| `tests/models/test_api_enum_parity.py` | `parents[2]` | `from tests.paths import BACKEND_ROOT` |

`tests/paths.py` 保留现有 `BACKEND_ROOT / PACKAGES / MILES_AI / MILES_SERVER`，
并新增 `TESTS_ROOT`（供结构守卫按目录枚举）。收尾断言 `rg 'parents\[' backend/tests` 只剩 `paths.py` 自身。

另同步 9 处 docstring 里的 `tests/<旧路径>` 引用（如 `tests/rag/test_parse_degradation_diagnosability.py`、
`tests/infra/test_loop_aware_engine.py` 自指）。

### 4.4 防退化守卫 `tests/test_tests_layout.py`

把「结构」固化成可执行契约，避免再次漂移：

1. `tests/` 一级目录 ∈ `{README.md, conftest.py, paths.py, test_*.py, integration, miles_common, miles_exec, miles_core,
   miles_ai, miles_portal, miles_admin, miles_openapi, miles_server, miles_worker, miles_runner}`；
2. `tests/miles_<pkg>/**` 下每个 `test_*.py` 至少有一条 import 语句 import 了该包（宽松版：只判包前缀，
   不判到具体目录，避免把跨域用例判死）。**唯一登记例外**：`miles_server/scripts/seed/test_model_catalog_seed.py`
   以路径读取被测源码做文本断言，无 import —— 走守卫内显式豁免集合并注明理由；
3. 全仓 `test_*.py` 基名唯一（无 `__init__.py` 时 pytest `prepend` 模式的硬约束）。

### 4.5 文档同步

- `backend/tests/README.md`：目录树与运行示例；
- `docs/architecture/layering.md` §7「测试布局」：目录树与守卫清单；
- `backend/README.md` 目录结构表（`tests/` 一行说明改为「按包镜像」）；
- **活引用**（约 25 处）：测试 docstring（7 处）、`packages/` 源码注释（18 处）、`docs/guides/*` 与 `docs/architecture/*`、`backend/pyproject.toml` 里的旧测试路径文字，一并更正为迁移后的路径；
  历史留档（`docs/superpowers/specs/**`、`.superpowers/**`、一次性 codemod `backend/tools/rename_to_workspace.py`）**不改**，同 alembic 版本脚本的冻结口径。

### 4.6 验证口径

| 检查 | 判据 |
|---|---|
| 用例集合不变 | 迁移前后 `pytest --collect-only -q` 的用例 ID **集合**（去掉路径前缀后按函数名比对）逐条一致：总数 1513 + 本次新增守卫 3 = 1516，`diff` 只允许出现这 3 个新名字 |
| 全量通过 | `cd backend && python -m pytest -q` 全绿（1516 passed） |
| 基名唯一 | 守卫 3；迁移前已校验一次（205 个目标无重名，`test_p1_features` 拆分为 2 个不同基名） |
| 无硬编码深度 | `rg 'parents\[' backend/tests` 只剩 `paths.py` |
| 包前缀自洽 | 守卫 2 |

## 5. 风险与回退

| 风险 | 处置 |
|---|---|
| 搬迁漏改路径引用（`parents[N]`、docstring、`tests.paths` 相对位置） | 分批 pytest + 收尾全量 + 守卫 2/3 |
| 用例被 pytest 漏收（目录名变化、基名冲突） | 收尾比对 `--collect-only` 用例集合，总数必须 1513（`test_p1_features.py` 的 2 个用例拆到两个文件，用例数不变） |
| 文档与实现不同步 | 第 5 批同批提交三份文档 |
| 回退 | 每批一个提交，`git revert` 即可逐步回退；无内容改动，回退无冲突 |

## 附录 A：逐文件映射

`→` 左侧为源（迁移前路径），右侧为目标目录与文件基名。`.py` 后缀省略。

```text
tests/ 根 (4)                                        → tests/                              test_l3_neutral_imports, test_no_blocking_calls_in_async, test_no_silent_broad_except, test_no_unreferenced_modules
tests/admin/ (5)
  → tests/miles_admin/app_ops/ (3)                     test_admin_admins, test_admin_billing_plan, test_admin_risk_enforce
  → tests/miles_admin/app_sys/ (1)                     test_admin_auth
  → tests/miles_admin/models/ (1)                      test_audit_log_indexes
tests/api/ (12)
  → tests/ (1)                                         test_domain_meta
  → tests/integration/ (1)                             test_module_smoke
  → tests/miles_core/web/ (1)                          test_platform_risk_middleware
  → tests/miles_openapi/views/ (1)                     test_a2a_server_api
  → tests/miles_portal/tenant/system/ (2)              test_system_management, test_user_batch
  → tests/miles_portal/tenant/{tasks,generative}/ (2)  test_p1_features → 拆分（§4.2）
  → tests/miles_server/ (1)                            test_health
  → tests/miles_server/apps/ (4)                       test_access_log_middleware, test_api_e2e, test_cors, test_exception_handlers
tests/flow/ (24)
  → tests/miles_ai/flow_runtime/ (15)                  test_compliance_node, test_control_nodes, test_flow_multimodal, test_flow_runtime_constants, test_flow_step_artifact, test_flow_template_graphs, test_flow_templates, test_generative_nodes, test_media_nodes, test_platform_tool_node, test_prompt_template_node, test_relevance_grade_flow, test_subflow, test_subflow_runtime, test_subflow_validate
  → tests/miles_ai/integrations/langgraph/ (6)         test_compile_error_details, test_langgraph_build, test_langgraph_compiler, test_langgraph_grading, test_langgraph_parallel, test_langgraph_rag
  → tests/miles_portal/tenant/flows/ (3)               test_flow_run_request, test_flow_tags, test_flow_versions_api
tests/infra/ (26)
  → tests/miles_ai/integrations/{langchain,langgraph,litellm}/ (3)  test_litellm_chat_stream, test_canvas_state_contract, test_litellm_adapter
  → tests/miles_ai/rag/ (1)                            test_upload_policy
  → tests/miles_common/ (1)                            test_idgen
  → tests/miles_core/ (4)                              test_field_crypto, test_logging, test_object_storage_settings, test_outbound_private_hosts_config
  → tests/miles_core/infra/ (1)                        test_otel_setup
  → tests/miles_core/infra/db/ (3)                     test_db_pool_settings, test_loop_aware_engine, test_run_worker_db_coro
  → tests/miles_core/infra/vector_store/ (4)           test_milvus_vector_store, test_storage_vector_factory, test_vector_store_langchain, test_weaviate_collection
  → tests/miles_core/models/ (1)                       test_audit_log_models
  → tests/miles_core/utils/ (1)                        test_system_config_value
  → tests/miles_portal/deletion/ (1)                   test_deletion_cascade
  → tests/miles_portal/tenant/models/ (1)              test_api_key_validation
  → tests/miles_portal/tenant/system/ (1)              test_infra
  → tests/miles_server/ (1)                            test_trace_id
  → tests/miles_server/scripts/seed/ (1)               test_model_catalog_seed
  → tests/miles_worker/ (2)                            test_celery_config, test_celery_task_names
tests/integration/ (1)                               → tests/integration/                  test_integration_pipeline
tests/marketplace/ (2)                               → tests/miles_portal/{marketplace,tenant/marketplace}/  test_marketplace_review_mode, test_upgrade_diff
tests/mcp/ (6)
  → tests/miles_ai/integrations/langchain/ (1)         test_mcp_function_calling
  → tests/miles_exec/mcp/ (2)                          test_runner_mcp_stdio, test_runner_spec
  → tests/miles_portal/tenant/mcp/ (2)                 test_legacy_sse_transport, test_mcp_client
  → tests/miles_server/scripts/seed/ (1)               test_seed_mcp
tests/media/ (7)
  → tests/miles_ai/integrations/generative/ (5)        test_dashscope_t2i, test_dashscope_video_frames, test_image_b64_decoding, test_volcengine_image, test_volcengine_video
  → tests/miles_portal/tenant/media_assets/ (2)        test_media_assets, test_video_cover
tests/models/ (4)
  → tests/ (3)                                         test_api_enum_parity, test_enum_contract, test_orm_registry_completeness
  → tests/miles_core/models/ (1)                       test_compliance_pipeline
tests/rag/ (22)
  → tests/miles_ai/rag/ (11)                           test_chunk_splitter, test_generate_rag_answer, test_hybrid_retrieval, test_ingest_page_no, test_parse_degradation_diagnosability, test_parse_loaders, test_rag_pipeline_ingest, test_rerank_retrieve, test_upload_policy_alignment, test_video_frames, test_video_ingest
  → tests/miles_ai/integrations/embeddings/ (2)        test_clip_visual_search, test_embedding_providers
  → tests/miles_ai/integrations/langgraph/ (3)         test_rag_answer_stream, test_rag_multimodal, test_rag_qa_nodes_share_generate
  → tests/miles_ai/integrations/rerank/ (1)            test_rerank_providers
  → tests/miles_portal/deletion/ (1)                   test_document_cleanup
  → tests/miles_portal/tenant/kb/ (4)                  test_embedding_models, test_ingest_failure, test_kb_document_delete, test_kb_service_embeddings
tests/tenant/a2a/ (4)                                → tests/miles_portal/tenant/a2a/      test_a2a_audit, test_a2a_rate_limit, test_a2a_server_card, test_a2a_task_resubscribe
tests/tenant/agents/ (25)
  → tests/miles_ai/integrations/deepagents/ (1)        test_deepagents_orchestrator
  → tests/miles_portal/tenant/a2a/ (5)                 test_a2a_card_client, test_a2a_client_auth, test_a2a_client_invoke, test_a2a_extract_text, test_a2a_invoke_rules
  → tests/miles_portal/tenant/agents/ (19)             test_agent_api_keys, test_agent_chat_io_shim, test_agent_chat_rag_flow_context, test_agent_chat_ws, test_agent_skill_kb_routing, test_agent_stats, test_api_access, test_call_records, test_chat_artifact_sync, test_chat_as_child, test_chat_as_child_simple, test_chat_entry_routing, test_chat_rag_connection_release, test_chat_sessions, test_chat_sessions_persist_turn, test_job_watch, test_multimodal_chat, test_rag_usage_accumulation, test_sub_agents_cycle
tests/tenant/attachments/ (3)                        → tests/miles_portal/tenant/attachments/  test_attachment_read_bytes, test_flow_media_reader, test_session_media_reader
tests/tenant/compliance/ (1)                         → tests/miles_portal/tenant/compliance/   test_scan_words_loader
tests/tenant/flows/ (2)                              → tests/miles_portal/tenant/flows/     test_run_context_session, test_subflow_loader
tests/tenant/generative/ (16)
  → tests/miles_ai/integrations/generative/ (5)        test_generative_model_resolve, test_generative_policy, test_image_prompt_guard, test_job_execution_runner, test_progress_session
  → tests/miles_core/models/ (2)                       test_generative_job_cancel, test_generative_jobs
  → tests/miles_portal/tenant/generative/ (9)          test_generative_image, test_generative_image_async, test_generative_job_list, test_generative_job_retry, test_generative_job_watch, test_generative_quota, test_generative_video, test_job_execution_submitters, test_job_stream_events
tests/tenant/hooks/ (7)
  → tests/miles_common/ (1)                            test_cron
  → tests/miles_portal/tenant/hooks/ (6)               test_hook_events, test_hook_http_executor, test_hook_meta, test_hook_python_executor, test_invoke_tenant_hook, test_python_hook
tests/tenant/kb/ (3)
  → tests/miles_portal/tenant/attachments/ (2)         test_attachment_content, test_attachments
  → tests/miles_portal/tenant/kb/ (1)                  test_kb_quota
tests/tenant/mcp/ (2)                                → tests/miles_portal/tenant/mcp[/runner]/  test_mcp_runner_audit, test_record_runner_session
tests/tenant/models/ (3)                             → tests/miles_portal/tenant/models/    test_chat_usage_accumulation, test_chat_usage_sink_session, test_flow_usage_sink
tests/tenant/prompts/ (1)                            → tests/miles_portal/tenant/prompts/   test_template_loader
tests/tenant/skills/ (9)                             → tests/miles_portal/tenant/skills/    test_agent_multi_skill_binding, test_skill_export_zip, test_skill_file_delete, test_skill_import_git_url, test_skill_import_zip_limits, test_skill_layout, test_skill_md, test_skill_run_script, test_skill_runtime_integration
tests/tenant/system/ (1)                             → tests/miles_portal/tenant/system/    test_user_service
tests/tenant/tools/ (18)
  → tests/miles_ai/integrations/langchain/ (4)         test_builtin_opt_in, test_knowledge_search_coexistence, test_tool_agent_loop, test_toolkit_contract
  → tests/miles_core/ (1)                              test_url_security
  → tests/miles_exec/sandbox/ (3)                      test_script_exec, test_script_stdlib, test_script_validate
  → tests/miles_portal/tenant/tools/ (10)              test_agent_executor, test_compliance_check_text, test_flow_invoker_session, test_invoke_custom_script, test_invoke_tool_with_context, test_run_flow_once, test_tools_catalog, test_tools_confirmation, test_tools_invoke, test_tools_parameters
tests/worker/ (1)                                    → tests/miles_worker/tasks/           test_generative_tasks
```

### 附录 A 中的判断说明

| 文件 | 为什么不按「最深 import」自动归类 |
|---|---|
| `api/test_api_e2e.py` | import 里有 `tenant.flows.schemas`，但断言对象是 `create_app()` 装配后的整链（R2） |
| `api/test_a2a_server_api.py` | 断言路由装配与响应形态，被测视图模块是 `miles_openapi.views.a2a_server`（R3） |
| `api/test_module_smoke.py` | 跨 `miles_ai` + `miles_portal` 的 import 冒烟，无单一被测模块（R3） |
| `api/test_domain_meta.py` | 聚合 18 个租户域的 `meta.py`，跨域契约（R3） |
| `models/test_enum_contract.py` | 跨 `miles_core` + `miles_portal` 的枚举契约，非单包（R3） |
| `models/test_compliance_pipeline.py` | 主对象是 `miles_core.models.compliance.pipeline`，portal shim 仅作对照 |
| `tenant/tools/test_compliance_check_text.py` | 名字含 compliance，实际被测是 `tenant/tools/handlers` |
| `tenant/tools/test_url_security.py` | 文件名像工具域，实际被测是 `miles_core.url_security` |
| `tenant/agents/test_rag_usage_accumulation.py` | 名字含 rag，实际是被测是 agent 会话内的用量累计（保留在 agents 域） |
| `tenant/agents/test_a2a_*.py` (5) | 被测是 `tenant/a2a` 的出站客户端，从 agents 域纠偏到 a2a 域 |
| `tenant/kb/test_attachment*.py` (2) | 被测是 `tenant/attachments`，从 kb 域纠偏 |
| `flow/test_compliance_node.py`、`flow/test_media_nodes.py` | 被测是 flow_runtime 的画布节点，非 core 的模型/常量 |
| `flow/test_flow_multimodal.py` | 8 个用例里 6 个（含全部 `patch` 目标）打 `miles_ai.flow_runtime` 的 `llm_call` / `media_refs_from_run` / `run_compiled_canvas`，只有 2 个碰 portal 的 `FlowRunRequest`；按 R1 归最深 import（终审纠偏，初版误归 `tenant/flows`） |
| `tenant/media_assets/test_video_cover.py` | 5:5 混合（`miles_ai.integrations.video.cover.extract_video_cover_jpeg` vs portal `MediaAssetOut`），无明显更深一侧，就近归 media_assets |
| `flow/test_relevance_grade_flow.py`、`flow/test_subflow.py` | 被测是 flow_runtime 的节点与子流，非 langgraph 编译层 |
| `infra/test_celery_*.py` (2) | 被测是 Celery app 与任务名（`miles_worker`） |
| `infra/test_audit_log_models.py` | 被测是 ORM 定义（`miles_core.models`） |
| `rag/test_rerank_retrieve.py` | 被测是 `miles_ai.rag.retrieve`，最深 import 命中的是 `miles_core.models.model.catalog` |
| `tenant/generative/test_generative_job_cancel.py`、`test_generative_jobs.py` | 名称像生成任务 API，实际只 import `miles_core.models.model.generative_job` 并断言枚举值，按 R1 归 `tests/miles_core/models/` |
