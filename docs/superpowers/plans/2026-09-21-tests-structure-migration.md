# tests 目录按 packages 镜像迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `backend/tests/` 从「单包时代的域目录」搬迁为按 `backend/packages/` 镜像的结构（一级目录 = 被测包，深层 = 包内模块层），用例集合与行为零变化。

**Architecture:** 5 批 `git mv` 纯搬迁，每批跑该批目标目录的 pytest 并单独提交；内容改动仅限三类：① `tests/api/test_p1_features.py` 按域拆成 2 个文件；② 4 处 `parents[N]` 路径推导改走 `tests.paths`；③ 4 处「用例之间互相 import」的模块路径同步改（`_usage_doubles`、`test_litellm_adapter`）。收尾新增结构守卫 `tests/test_tests_layout.py` 与文档/注释里的旧路径同步。

**Tech Stack:** pytest（`asyncio_mode = "auto"`）、git、ruff（仅 `format --check` 形态校验，本计划不产生源码改动）。

**设计依据：** `docs/superpowers/specs/2026-09-21-tests-structure-design.md`（含附录 A 逐文件映射）。

## Global Constraints

- 所有命令在 `/Users/xiezhigang/Projects/miles/MilesAI/backend` 下执行。
- 测试一律用 `.venv/bin/python -m pytest`：`tests.paths` / `tests.conftest` 依赖 `backend/` 在 `sys.path`（裸 `pytest` 不保证）；CI 与 Makefile 用的也是 `python -m pytest -q`。
- 基线（2026-09-21，main `8135d669`）：`1513 passed in 38.15s`；快照见 Task 0。
- 纯搬迁：**禁止**改用例逻辑、断言、fixture、`monkeypatch`/`patch` 目标字符串。
- **禁止**重命名测试文件。唯一例外：`tests/api/test_p1_features.py` 按域拆为两个文件（Task 4 Step 3）。
- 每批结束后 `git status --porcelain` 只允许出现 `R ` 前缀行（重命名）；出现 `M`/`A`/`D` 需排查。
- 每批一个提交，message 用简体中文 Conventional Commits：`refactor(tests): …`。
- 每批预期用例数（基线实测，2026-09-21）：Task 1 = 105、Task 2 = 78、Task 3 = 433、Task 4 = 767（含拆分出的 2 个用例）、Task 5 = 114；加上留原位的 4 个根级 AST 守卫 16 个用例，合计 1513。若期间 `main` 上有新增用例，以「0 failed」+ 集合快照比对为准。

---

### Task 0: 记录迁移前基线

**Files:**
- 无改动（只产出 `/tmp` 下的快照）

**Interfaces:**
- Produces: `/tmp/tests-names-before.txt`（用例名集合，Task 8 用它比对）、`/tmp/tests-files-before.txt`（文件清单）

- [ ] **Step 1: 记录用例名集合（与文件路径无关，只留 `::` 之后的部分）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/tests-names-before.txt
wc -l /tmp/tests-names-before.txt
```

Expected: `1513 /tmp/tests-names-before.txt`

- [ ] **Step 2: 记录文件清单与工作区状态**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git ls-files tests | sort > /tmp/tests-files-before.txt
wc -l /tmp/tests-files-before.txt
git status --porcelain
```

Expected: `213 /tmp/tests-files-before.txt` = 209 个 `test_*.py` + 3 个根级基础设施文件（`README.md`、`conftest.py`、`paths.py`）+ 1 个共享辅助模块（`tenant/models/_usage_doubles.py`）；`git status --porcelain` 输出为空。

- [ ] **Step 3: 记录「用例之间互相 import」的现状（搬迁后这些导入路径要同步改）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "from tests\.(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)" tests > /tmp/tests-cross-imports-before.txt
cat /tmp/tests-cross-imports-before.txt
```

Expected: 4 处命中，且仅这 4 处：

```text
tests/infra/test_litellm_chat_stream.py:8:from tests.infra.test_litellm_adapter import _model
tests/rag/test_rag_answer_stream.py:11:from tests.infra.test_litellm_adapter import _model
tests/tenant/models/test_chat_usage_accumulation.py:15:from tests.tenant.models._usage_doubles import _cm, _ShortSession
tests/tenant/models/test_chat_usage_sink_session.py:21:from tests.tenant.models._usage_doubles import _cm, _ShortSession
```

若实际多于 4 处，说明期间又新增了跨模块导入：按同一规则（提供方的新路径）在对应批次里改掉，并在 Task 8 Step 3b 用下面的命令确认归零：

```bash
rg -n "from tests\.(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)" tests
```

---

### Task 1: 搬迁 `miles_common` / `miles_exec` / `miles_worker` / `miles_server` / `miles_openapi`（19 个文件）

**Files:**
- Modify（仅重命名）：见 Step 1 命令块

**Interfaces:**
- Consumes: Task 0 的基线
- Produces: `tests/miles_common/`、`tests/miles_exec/{mcp,sandbox}/`、`tests/miles_worker/{,tasks}/`、`tests/miles_server/{,apps,scripts/seed}/`、`tests/miles_openapi/views/`

- [ ] **Step 1: 建目录并重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_common tests/miles_exec/mcp tests/miles_exec/sandbox tests/miles_openapi/views \
         tests/miles_server tests/miles_server/apps tests/miles_server/scripts/seed \
         tests/miles_worker tests/miles_worker/tasks
git mv tests/api/test_a2a_server_api.py tests/miles_openapi/views/test_a2a_server_api.py
git mv tests/api/test_access_log_middleware.py tests/miles_server/apps/test_access_log_middleware.py
git mv tests/api/test_api_e2e.py tests/miles_server/apps/test_api_e2e.py
git mv tests/api/test_cors.py tests/miles_server/apps/test_cors.py
git mv tests/api/test_exception_handlers.py tests/miles_server/apps/test_exception_handlers.py
git mv tests/api/test_health.py tests/miles_server/test_health.py
git mv tests/infra/test_celery_config.py tests/miles_worker/test_celery_config.py
git mv tests/infra/test_celery_task_names.py tests/miles_worker/test_celery_task_names.py
git mv tests/infra/test_idgen.py tests/miles_common/test_idgen.py
git mv tests/infra/test_model_catalog_seed.py tests/miles_server/scripts/seed/test_model_catalog_seed.py
git mv tests/infra/test_trace_id.py tests/miles_server/test_trace_id.py
git mv tests/mcp/test_runner_mcp_stdio.py tests/miles_exec/mcp/test_runner_mcp_stdio.py
git mv tests/mcp/test_runner_spec.py tests/miles_exec/mcp/test_runner_spec.py
git mv tests/mcp/test_seed_mcp.py tests/miles_server/scripts/seed/test_seed_mcp.py
git mv tests/tenant/hooks/test_cron.py tests/miles_common/test_cron.py
git mv tests/tenant/tools/test_script_exec.py tests/miles_exec/sandbox/test_script_exec.py
git mv tests/tenant/tools/test_script_stdlib.py tests/miles_exec/sandbox/test_script_stdlib.py
git mv tests/tenant/tools/test_script_validate.py tests/miles_exec/sandbox/test_script_validate.py
git mv tests/worker/test_generative_tasks.py tests/miles_worker/tasks/test_generative_tasks.py
```

- [ ] **Step 2: 确认只有重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git status --porcelain | grep -v '^R ' ; git status --porcelain | wc -l
```

Expected: 第一条命令无输出；第二条为 `19`。

- [ ] **Step 3: 跑该批目标目录**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/miles_common tests/miles_exec tests/miles_worker tests/miles_server tests/miles_openapi
```

Expected: `105 passed`（0 failed）

- [ ] **Step 4: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
refactor(tests): 测试目录按包搬迁第一批（common/exec/worker/server/openapi）

单包时代的域目录里混着 5 个包的用例（infra/、mcp/、worker/、tenant/tools/ 等），
先搬体量最小的一批，验证「目录 ⇔ 包」的映射与分批验证节奏。
MSG
```

---

### Task 2: 搬迁 `miles_core`（19 个文件，含 2 处路径推导改写）

**Files:**
- Modify（重命名）：见 Step 1
- Modify（内容）：`tests/miles_core/infra/db/test_loop_aware_engine.py:273-276`、`tests/miles_core/infra/db/test_run_worker_db_coro.py:139`

**Interfaces:**
- Consumes: Task 1 的提交
- Produces: `tests/miles_core/{,infra,infra/db,infra/vector_store,models,utils,web}/`

- [ ] **Step 1: 建目录并重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_core tests/miles_core/infra tests/miles_core/infra/db tests/miles_core/infra/vector_store \
         tests/miles_core/models tests/miles_core/utils tests/miles_core/web
git mv tests/api/test_platform_risk_middleware.py tests/miles_core/web/test_platform_risk_middleware.py
git mv tests/infra/test_audit_log_models.py tests/miles_core/models/test_audit_log_models.py
git mv tests/infra/test_db_pool_settings.py tests/miles_core/infra/db/test_db_pool_settings.py
git mv tests/infra/test_field_crypto.py tests/miles_core/test_field_crypto.py
git mv tests/infra/test_logging.py tests/miles_core/test_logging.py
git mv tests/infra/test_loop_aware_engine.py tests/miles_core/infra/db/test_loop_aware_engine.py
git mv tests/infra/test_milvus_vector_store.py tests/miles_core/infra/vector_store/test_milvus_vector_store.py
git mv tests/infra/test_object_storage_settings.py tests/miles_core/test_object_storage_settings.py
git mv tests/infra/test_otel_setup.py tests/miles_core/infra/test_otel_setup.py
git mv tests/infra/test_outbound_private_hosts_config.py tests/miles_core/test_outbound_private_hosts_config.py
git mv tests/infra/test_run_worker_db_coro.py tests/miles_core/infra/db/test_run_worker_db_coro.py
git mv tests/infra/test_storage_vector_factory.py tests/miles_core/infra/vector_store/test_storage_vector_factory.py
git mv tests/infra/test_system_config_value.py tests/miles_core/utils/test_system_config_value.py
git mv tests/infra/test_vector_store_langchain.py tests/miles_core/infra/vector_store/test_vector_store_langchain.py
git mv tests/infra/test_weaviate_collection.py tests/miles_core/infra/vector_store/test_weaviate_collection.py
git mv tests/models/test_compliance_pipeline.py tests/miles_core/models/test_compliance_pipeline.py
git mv tests/tenant/generative/test_generative_job_cancel.py tests/miles_core/models/test_generative_job_cancel.py
git mv tests/tenant/generative/test_generative_jobs.py tests/miles_core/models/test_generative_jobs.py
git mv tests/tenant/tools/test_url_security.py tests/miles_core/test_url_security.py
```

- [ ] **Step 2: 改写 `test_loop_aware_engine.py` 的路径推导（深度变了，`parents[2]` 会指错）**

原文（`tests/miles_core/infra/db/test_loop_aware_engine.py` 第 273–276 行）：

```python
# 由本文件位置推导仓库根，与 ``test_run_worker_db_coro.py`` 的 ``_WORKER_SRC_ROOT`` 同法（不写
# 死绝对路径）。``tests/infra/`` 的 parents[2] 即 ``backend/``。
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_HEALTH_CHECKS_SRC = _BACKEND_ROOT / "packages" / "miles-core" / "src" / "miles_core" / "utils" / "health_checks.py"
```

替换为：

```python
# 路径常量统一来自 ``tests.paths``：本文件在 ``tests/miles_core/infra/db/``，深度已变，
# 不能再靠 ``parents`` 猜仓库根（层级会随目录漂移）。
_BACKEND_ROOT = BACKEND_ROOT
_HEALTH_CHECKS_SRC = _BACKEND_ROOT / "packages" / "miles-core" / "src" / "miles_core" / "utils" / "health_checks.py"
```

> 注：注释刻意不写字面量 `parents[N]`——Task 3 Step 4 与 Task 8 Step 3 的验收命令是
> `rg "parents\[" tests/miles_ai` / `rg "parents\[" tests`，写全会让验收命中该注释。

并在 import 区的第一方分组里加（紧挨现有的 `from miles_core…` 那几行、与它们同组且不加空行——ruff isort 视 `tests` 与 `miles_*` 为同一组，见 `tests/test_orm_registry_completeness.py` 的写法）：

```python
from tests.paths import BACKEND_ROOT
```

该文件的 `Path` **只在此行使用**（已核对：`rg -n '\bPath\b'` 仅命中第 15 行 import 与第 275 行），故替换后必须删掉第 15 行的 `from pathlib import Path`，否则 ruff 报 F401。

- [ ] **Step 3: 改写 `test_run_worker_db_coro.py` 的路径推导**

原文（`tests/miles_core/infra/db/test_run_worker_db_coro.py` 第 139 行）：

```python
_WORKER_SRC_ROOT = Path(__file__).resolve().parents[2] / "packages" / "miles-worker" / "src"
```

替换为：

```python
_WORKER_SRC_ROOT = PACKAGES / "miles-worker" / "src"
```

并在该文件 import 区的第一方分组里加（与 `from miles_*` 同组，不加空行）：

```python
from tests.paths import PACKAGES
```

该文件的 `Path` **只在此行使用**（已核对：`rg -n '\bPath\b'` 仅命中第 16 行 import 与第 139 行），故替换后必须删掉第 16 行的 `from pathlib import Path`，否则 ruff 报 F401。

- [ ] **Step 4: 跑该批目标目录**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/miles_core
```

Expected: `78 passed`

- [ ] **Step 5: 确认改动范围**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git status --porcelain | grep -v '^R ' ; git status --porcelain | grep '^ M\|^M' | cut -c4-
```

Expected: 只出现 `tests/miles_core/infra/db/test_loop_aware_engine.py` 与 `tests/miles_core/infra/db/test_run_worker_db_coro.py` 两个 `M`（其余为重命名）。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
refactor(tests): 测试目录按包搬迁第二批（miles_core）

infra/ 里 14 个用例实际测的是 miles_core；顺带把两处 parents[2] 换成 tests.paths
常量，避免目录变深后路径推导指错 backend 根。
MSG
```

---

### Task 3: 搬迁 `miles_ai`（57 个文件，含 1 处路径推导改写）

**Files:**
- Modify（重命名）：见 Step 1
- Modify（内容）：`tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py:9,20`

**Interfaces:**
- Consumes: Task 2 的提交
- Produces: `tests/miles_ai/{rag,flow_runtime,integrations/{langchain,langgraph,generative,embeddings,rerank,litellm,deepagents}}/`

- [ ] **Step 1: 建目录并重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_ai/flow_runtime tests/miles_ai/rag \
         tests/miles_ai/integrations/deepagents tests/miles_ai/integrations/embeddings \
         tests/miles_ai/integrations/generative tests/miles_ai/integrations/langchain \
         tests/miles_ai/integrations/langgraph tests/miles_ai/integrations/litellm \
         tests/miles_ai/integrations/rerank
git mv tests/flow/test_compile_error_details.py tests/miles_ai/integrations/langgraph/test_compile_error_details.py
git mv tests/flow/test_compliance_node.py tests/miles_ai/flow_runtime/test_compliance_node.py
git mv tests/flow/test_control_nodes.py tests/miles_ai/flow_runtime/test_control_nodes.py
git mv tests/flow/test_flow_runtime_constants.py tests/miles_ai/flow_runtime/test_flow_runtime_constants.py
git mv tests/flow/test_flow_step_artifact.py tests/miles_ai/flow_runtime/test_flow_step_artifact.py
git mv tests/flow/test_flow_template_graphs.py tests/miles_ai/flow_runtime/test_flow_template_graphs.py
git mv tests/flow/test_flow_templates.py tests/miles_ai/flow_runtime/test_flow_templates.py
git mv tests/flow/test_generative_nodes.py tests/miles_ai/flow_runtime/test_generative_nodes.py
git mv tests/flow/test_langgraph_build.py tests/miles_ai/integrations/langgraph/test_langgraph_build.py
git mv tests/flow/test_langgraph_compiler.py tests/miles_ai/integrations/langgraph/test_langgraph_compiler.py
git mv tests/flow/test_langgraph_grading.py tests/miles_ai/integrations/langgraph/test_langgraph_grading.py
git mv tests/flow/test_langgraph_parallel.py tests/miles_ai/integrations/langgraph/test_langgraph_parallel.py
git mv tests/flow/test_langgraph_rag.py tests/miles_ai/integrations/langgraph/test_langgraph_rag.py
git mv tests/flow/test_flow_multimodal.py tests/miles_ai/flow_runtime/test_flow_multimodal.py
git mv tests/flow/test_media_nodes.py tests/miles_ai/flow_runtime/test_media_nodes.py
git mv tests/flow/test_platform_tool_node.py tests/miles_ai/flow_runtime/test_platform_tool_node.py
git mv tests/flow/test_prompt_template_node.py tests/miles_ai/flow_runtime/test_prompt_template_node.py
git mv tests/flow/test_relevance_grade_flow.py tests/miles_ai/flow_runtime/test_relevance_grade_flow.py
git mv tests/flow/test_subflow.py tests/miles_ai/flow_runtime/test_subflow.py
git mv tests/flow/test_subflow_runtime.py tests/miles_ai/flow_runtime/test_subflow_runtime.py
git mv tests/flow/test_subflow_validate.py tests/miles_ai/flow_runtime/test_subflow_validate.py
git mv tests/infra/test_canvas_state_contract.py tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py
git mv tests/infra/test_litellm_adapter.py tests/miles_ai/integrations/litellm/test_litellm_adapter.py
git mv tests/infra/test_litellm_chat_stream.py tests/miles_ai/integrations/langchain/test_litellm_chat_stream.py
git mv tests/infra/test_upload_policy.py tests/miles_ai/rag/test_upload_policy.py
git mv tests/mcp/test_mcp_function_calling.py tests/miles_ai/integrations/langchain/test_mcp_function_calling.py
git mv tests/media/test_dashscope_t2i.py tests/miles_ai/integrations/generative/test_dashscope_t2i.py
git mv tests/media/test_dashscope_video_frames.py tests/miles_ai/integrations/generative/test_dashscope_video_frames.py
git mv tests/media/test_image_b64_decoding.py tests/miles_ai/integrations/generative/test_image_b64_decoding.py
git mv tests/media/test_volcengine_image.py tests/miles_ai/integrations/generative/test_volcengine_image.py
git mv tests/media/test_volcengine_video.py tests/miles_ai/integrations/generative/test_volcengine_video.py
git mv tests/rag/test_chunk_splitter.py tests/miles_ai/rag/test_chunk_splitter.py
git mv tests/rag/test_clip_visual_search.py tests/miles_ai/integrations/embeddings/test_clip_visual_search.py
git mv tests/rag/test_embedding_providers.py tests/miles_ai/integrations/embeddings/test_embedding_providers.py
git mv tests/rag/test_generate_rag_answer.py tests/miles_ai/rag/test_generate_rag_answer.py
git mv tests/rag/test_hybrid_retrieval.py tests/miles_ai/rag/test_hybrid_retrieval.py
git mv tests/rag/test_ingest_page_no.py tests/miles_ai/rag/test_ingest_page_no.py
git mv tests/rag/test_parse_degradation_diagnosability.py tests/miles_ai/rag/test_parse_degradation_diagnosability.py
git mv tests/rag/test_parse_loaders.py tests/miles_ai/rag/test_parse_loaders.py
git mv tests/rag/test_rag_answer_stream.py tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py
git mv tests/rag/test_rag_multimodal.py tests/miles_ai/integrations/langgraph/test_rag_multimodal.py
git mv tests/rag/test_rag_pipeline_ingest.py tests/miles_ai/rag/test_rag_pipeline_ingest.py
git mv tests/rag/test_rag_qa_nodes_share_generate.py tests/miles_ai/integrations/langgraph/test_rag_qa_nodes_share_generate.py
git mv tests/rag/test_rerank_providers.py tests/miles_ai/integrations/rerank/test_rerank_providers.py
git mv tests/rag/test_rerank_retrieve.py tests/miles_ai/rag/test_rerank_retrieve.py
git mv tests/rag/test_upload_policy_alignment.py tests/miles_ai/rag/test_upload_policy_alignment.py
git mv tests/rag/test_video_frames.py tests/miles_ai/rag/test_video_frames.py
git mv tests/rag/test_video_ingest.py tests/miles_ai/rag/test_video_ingest.py
git mv tests/tenant/agents/test_deepagents_orchestrator.py tests/miles_ai/integrations/deepagents/test_deepagents_orchestrator.py
git mv tests/tenant/generative/test_generative_model_resolve.py tests/miles_ai/integrations/generative/test_generative_model_resolve.py
git mv tests/tenant/generative/test_generative_policy.py tests/miles_ai/integrations/generative/test_generative_policy.py
git mv tests/tenant/generative/test_image_prompt_guard.py tests/miles_ai/integrations/generative/test_image_prompt_guard.py
git mv tests/tenant/generative/test_job_execution_runner.py tests/miles_ai/integrations/generative/test_job_execution_runner.py
git mv tests/tenant/generative/test_progress_session.py tests/miles_ai/integrations/generative/test_progress_session.py
git mv tests/tenant/tools/test_builtin_opt_in.py tests/miles_ai/integrations/langchain/test_builtin_opt_in.py
git mv tests/tenant/tools/test_knowledge_search_coexistence.py tests/miles_ai/integrations/langchain/test_knowledge_search_coexistence.py
git mv tests/tenant/tools/test_tool_agent_loop.py tests/miles_ai/integrations/langchain/test_tool_agent_loop.py
git mv tests/tenant/tools/test_toolkit_contract.py tests/miles_ai/integrations/langchain/test_toolkit_contract.py
```

- [ ] **Step 2: 改写 `test_canvas_state_contract.py` 的路径推导**

原文（`tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py` 第 18–21 行）：

```python
# tests/infra/<this> → backend/（显式路径单跑时 ``tests.paths`` 不可导入，故本地推导）
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_COMPILER_DIR = _BACKEND_DIR / "packages" / "miles-ai" / "src" / "miles_ai" / "integrations" / "langgraph" / "compiler"
```

替换为：

```python
# 路径常量统一来自 ``tests.paths``（本文件已搬到 tests/miles_ai/integrations/langgraph/，
# 目录深度变化后 ``parents`` 推导不再可靠）。
_BACKEND_DIR = BACKEND_ROOT
_COMPILER_DIR = _BACKEND_DIR / "packages" / "miles-ai" / "src" / "miles_ai" / "integrations" / "langgraph" / "compiler"
```

并把 import 区的 `from miles_ai.integrations.langgraph.compiler.state import CanvasGraphState` 之后加一行（同一分组，不加空行）：

```python
from tests.paths import BACKEND_ROOT
```

该文件的 `Path` **只在此处使用**（已核对：`rg -n '\bPath\b'` 仅命中第 16 行 import 与第 21 行），故同时删掉第 16 行的 `from pathlib import Path`（否则 ruff F401），并删掉第 20 行旧注释（其理由「显式路径单跑时 `tests.paths` 不可导入」只对裸 `pytest` 成立；项目标准入口是 `make test-backend` → `cd backend && python -m pytest`，cwd 进 `sys.path`，`tests/` 下已有 `test_model_catalog_seed.py` 等多例这样导入）。

同时把第 10 行 docstring 里的 `风格对齐 ``tests/test_l3_neutral_imports.py``（同样是源码扫描守卫）。` 保持不变（该文件仍在 `tests/` 根，路径未变）。

- [ ] **Step 2b: 改写跨用例模块导入（`test_litellm_adapter._model`，2 处）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "from tests\.infra\.test_litellm_adapter" tests
```

预期命中 2 处：

- `tests/miles_ai/integrations/langchain/test_litellm_chat_stream.py:8`
- `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:11`

两处都由

```python
from tests.infra.test_litellm_adapter import _model
```

改为

```python
from tests.miles_ai.integrations.litellm.test_litellm_adapter import _model
```

（共用桩函数 `_model` 的提供方同批搬到 `tests/miles_ai/integrations/litellm/`。基名 `test_litellm_adapter` 全仓唯一，pytest 不会因该导入把同一文件重复收集。）

- [ ] **Step 3: 跑该批目标目录**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/miles_ai
```

Expected: `433 passed`

- [ ] **Step 4: 检查该批是否还有硬编码深度**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "parents\[" tests/miles_ai
```

Expected: 无输出

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
refactor(tests): 测试目录按包搬迁第三批（miles_ai）

flow/、rag/、media/ 与 tenant/ 里的 AI 侧用例归位到 miles_ai 的 rag、flow_runtime、
integrations/*；画布 state 守卫的路径推导改走 tests.paths。
MSG
```

---

### Task 4: 搬迁 `miles_portal`（98 个文件 + 拆分 1 个文件）

**Files:**
- Modify（重命名）：见 Step 1
- Create: `tests/miles_portal/tenant/tasks/test_task_batch_cancel.py`、`tests/miles_portal/tenant/generative/test_generative_batch_cancel.py`
- Delete: `tests/api/test_p1_features.py`

**Interfaces:**
- Consumes: Task 3 的提交
- Produces: `tests/miles_portal/{tenant/*,marketplace,deletion}/`

- [ ] **Step 1: 建目录并重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_portal/deletion tests/miles_portal/marketplace \
         tests/miles_portal/tenant/a2a tests/miles_portal/tenant/agents tests/miles_portal/tenant/attachments \
         tests/miles_portal/tenant/compliance tests/miles_portal/tenant/flows tests/miles_portal/tenant/generative \
         tests/miles_portal/tenant/hooks tests/miles_portal/tenant/kb tests/miles_portal/tenant/marketplace \
         tests/miles_portal/tenant/mcp tests/miles_portal/tenant/mcp/runner tests/miles_portal/tenant/media_assets \
         tests/miles_portal/tenant/models tests/miles_portal/tenant/prompts tests/miles_portal/tenant/skills \
         tests/miles_portal/tenant/system tests/miles_portal/tenant/tasks tests/miles_portal/tenant/tools
git mv tests/api/test_system_management.py tests/miles_portal/tenant/system/test_system_management.py
git mv tests/api/test_user_batch.py tests/miles_portal/tenant/system/test_user_batch.py
git mv tests/flow/test_flow_run_request.py tests/miles_portal/tenant/flows/test_flow_run_request.py
git mv tests/flow/test_flow_tags.py tests/miles_portal/tenant/flows/test_flow_tags.py
git mv tests/flow/test_flow_versions_api.py tests/miles_portal/tenant/flows/test_flow_versions_api.py
git mv tests/infra/test_api_key_validation.py tests/miles_portal/tenant/models/test_api_key_validation.py
git mv tests/infra/test_deletion_cascade.py tests/miles_portal/deletion/test_deletion_cascade.py
git mv tests/infra/test_infra.py tests/miles_portal/tenant/system/test_infra.py
git mv tests/marketplace/test_marketplace_review_mode.py tests/miles_portal/marketplace/test_marketplace_review_mode.py
git mv tests/marketplace/test_upgrade_diff.py tests/miles_portal/tenant/marketplace/test_upgrade_diff.py
git mv tests/mcp/test_legacy_sse_transport.py tests/miles_portal/tenant/mcp/test_legacy_sse_transport.py
git mv tests/mcp/test_mcp_client.py tests/miles_portal/tenant/mcp/test_mcp_client.py
git mv tests/media/test_media_assets.py tests/miles_portal/tenant/media_assets/test_media_assets.py
git mv tests/media/test_video_cover.py tests/miles_portal/tenant/media_assets/test_video_cover.py
git mv tests/rag/test_document_cleanup.py tests/miles_portal/deletion/test_document_cleanup.py
git mv tests/rag/test_embedding_models.py tests/miles_portal/tenant/kb/test_embedding_models.py
git mv tests/rag/test_ingest_failure.py tests/miles_portal/tenant/kb/test_ingest_failure.py
git mv tests/rag/test_kb_document_delete.py tests/miles_portal/tenant/kb/test_kb_document_delete.py
git mv tests/rag/test_kb_service_embeddings.py tests/miles_portal/tenant/kb/test_kb_service_embeddings.py
git mv tests/tenant/a2a/test_a2a_audit.py tests/miles_portal/tenant/a2a/test_a2a_audit.py
git mv tests/tenant/a2a/test_a2a_rate_limit.py tests/miles_portal/tenant/a2a/test_a2a_rate_limit.py
git mv tests/tenant/a2a/test_a2a_server_card.py tests/miles_portal/tenant/a2a/test_a2a_server_card.py
git mv tests/tenant/a2a/test_a2a_task_resubscribe.py tests/miles_portal/tenant/a2a/test_a2a_task_resubscribe.py
git mv tests/tenant/agents/test_a2a_card_client.py tests/miles_portal/tenant/a2a/test_a2a_card_client.py
git mv tests/tenant/agents/test_a2a_client_auth.py tests/miles_portal/tenant/a2a/test_a2a_client_auth.py
git mv tests/tenant/agents/test_a2a_client_invoke.py tests/miles_portal/tenant/a2a/test_a2a_client_invoke.py
git mv tests/tenant/agents/test_a2a_extract_text.py tests/miles_portal/tenant/a2a/test_a2a_extract_text.py
git mv tests/tenant/agents/test_a2a_invoke_rules.py tests/miles_portal/tenant/a2a/test_a2a_invoke_rules.py
git mv tests/tenant/agents/test_agent_api_keys.py tests/miles_portal/tenant/agents/test_agent_api_keys.py
git mv tests/tenant/agents/test_agent_chat_io_shim.py tests/miles_portal/tenant/agents/test_agent_chat_io_shim.py
git mv tests/tenant/agents/test_agent_chat_rag_flow_context.py tests/miles_portal/tenant/agents/test_agent_chat_rag_flow_context.py
git mv tests/tenant/agents/test_agent_chat_ws.py tests/miles_portal/tenant/agents/test_agent_chat_ws.py
git mv tests/tenant/agents/test_agent_skill_kb_routing.py tests/miles_portal/tenant/agents/test_agent_skill_kb_routing.py
git mv tests/tenant/agents/test_agent_stats.py tests/miles_portal/tenant/agents/test_agent_stats.py
git mv tests/tenant/agents/test_api_access.py tests/miles_portal/tenant/agents/test_api_access.py
git mv tests/tenant/agents/test_call_records.py tests/miles_portal/tenant/agents/test_call_records.py
git mv tests/tenant/agents/test_chat_artifact_sync.py tests/miles_portal/tenant/agents/test_chat_artifact_sync.py
git mv tests/tenant/agents/test_chat_as_child.py tests/miles_portal/tenant/agents/test_chat_as_child.py
git mv tests/tenant/agents/test_chat_as_child_simple.py tests/miles_portal/tenant/agents/test_chat_as_child_simple.py
git mv tests/tenant/agents/test_chat_entry_routing.py tests/miles_portal/tenant/agents/test_chat_entry_routing.py
git mv tests/tenant/agents/test_chat_rag_connection_release.py tests/miles_portal/tenant/agents/test_chat_rag_connection_release.py
git mv tests/tenant/agents/test_chat_sessions.py tests/miles_portal/tenant/agents/test_chat_sessions.py
git mv tests/tenant/agents/test_chat_sessions_persist_turn.py tests/miles_portal/tenant/agents/test_chat_sessions_persist_turn.py
git mv tests/tenant/agents/test_job_watch.py tests/miles_portal/tenant/agents/test_job_watch.py
git mv tests/tenant/agents/test_multimodal_chat.py tests/miles_portal/tenant/agents/test_multimodal_chat.py
git mv tests/tenant/agents/test_rag_usage_accumulation.py tests/miles_portal/tenant/agents/test_rag_usage_accumulation.py
git mv tests/tenant/agents/test_sub_agents_cycle.py tests/miles_portal/tenant/agents/test_sub_agents_cycle.py
git mv tests/tenant/attachments/test_attachment_read_bytes.py tests/miles_portal/tenant/attachments/test_attachment_read_bytes.py
git mv tests/tenant/attachments/test_flow_media_reader.py tests/miles_portal/tenant/attachments/test_flow_media_reader.py
git mv tests/tenant/attachments/test_session_media_reader.py tests/miles_portal/tenant/attachments/test_session_media_reader.py
git mv tests/tenant/compliance/test_scan_words_loader.py tests/miles_portal/tenant/compliance/test_scan_words_loader.py
git mv tests/tenant/flows/test_run_context_session.py tests/miles_portal/tenant/flows/test_run_context_session.py
git mv tests/tenant/flows/test_subflow_loader.py tests/miles_portal/tenant/flows/test_subflow_loader.py
git mv tests/tenant/generative/test_generative_image.py tests/miles_portal/tenant/generative/test_generative_image.py
git mv tests/tenant/generative/test_generative_image_async.py tests/miles_portal/tenant/generative/test_generative_image_async.py
git mv tests/tenant/generative/test_generative_job_list.py tests/miles_portal/tenant/generative/test_generative_job_list.py
git mv tests/tenant/generative/test_generative_job_retry.py tests/miles_portal/tenant/generative/test_generative_job_retry.py
git mv tests/tenant/generative/test_generative_job_watch.py tests/miles_portal/tenant/generative/test_generative_job_watch.py
git mv tests/tenant/generative/test_generative_quota.py tests/miles_portal/tenant/generative/test_generative_quota.py
git mv tests/tenant/generative/test_generative_video.py tests/miles_portal/tenant/generative/test_generative_video.py
git mv tests/tenant/generative/test_job_execution_submitters.py tests/miles_portal/tenant/generative/test_job_execution_submitters.py
git mv tests/tenant/generative/test_job_stream_events.py tests/miles_portal/tenant/generative/test_job_stream_events.py
git mv tests/tenant/hooks/test_hook_events.py tests/miles_portal/tenant/hooks/test_hook_events.py
git mv tests/tenant/hooks/test_hook_http_executor.py tests/miles_portal/tenant/hooks/test_hook_http_executor.py
git mv tests/tenant/hooks/test_hook_meta.py tests/miles_portal/tenant/hooks/test_hook_meta.py
git mv tests/tenant/hooks/test_hook_python_executor.py tests/miles_portal/tenant/hooks/test_hook_python_executor.py
git mv tests/tenant/hooks/test_invoke_tenant_hook.py tests/miles_portal/tenant/hooks/test_invoke_tenant_hook.py
git mv tests/tenant/hooks/test_python_hook.py tests/miles_portal/tenant/hooks/test_python_hook.py
git mv tests/tenant/kb/test_attachment_content.py tests/miles_portal/tenant/attachments/test_attachment_content.py
git mv tests/tenant/kb/test_attachments.py tests/miles_portal/tenant/attachments/test_attachments.py
git mv tests/tenant/kb/test_kb_quota.py tests/miles_portal/tenant/kb/test_kb_quota.py
git mv tests/tenant/mcp/runner/test_record_runner_session.py tests/miles_portal/tenant/mcp/runner/test_record_runner_session.py
git mv tests/tenant/mcp/test_mcp_runner_audit.py tests/miles_portal/tenant/mcp/test_mcp_runner_audit.py
git mv tests/tenant/models/_usage_doubles.py tests/miles_portal/tenant/models/_usage_doubles.py
git mv tests/tenant/models/test_chat_usage_accumulation.py tests/miles_portal/tenant/models/test_chat_usage_accumulation.py
git mv tests/tenant/models/test_chat_usage_sink_session.py tests/miles_portal/tenant/models/test_chat_usage_sink_session.py
git mv tests/tenant/models/test_flow_usage_sink.py tests/miles_portal/tenant/models/test_flow_usage_sink.py
git mv tests/tenant/prompts/test_template_loader.py tests/miles_portal/tenant/prompts/test_template_loader.py
git mv tests/tenant/skills/test_agent_multi_skill_binding.py tests/miles_portal/tenant/skills/test_agent_multi_skill_binding.py
git mv tests/tenant/skills/test_skill_export_zip.py tests/miles_portal/tenant/skills/test_skill_export_zip.py
git mv tests/tenant/skills/test_skill_file_delete.py tests/miles_portal/tenant/skills/test_skill_file_delete.py
git mv tests/tenant/skills/test_skill_import_git_url.py tests/miles_portal/tenant/skills/test_skill_import_git_url.py
git mv tests/tenant/skills/test_skill_import_zip_limits.py tests/miles_portal/tenant/skills/test_skill_import_zip_limits.py
git mv tests/tenant/skills/test_skill_layout.py tests/miles_portal/tenant/skills/test_skill_layout.py
git mv tests/tenant/skills/test_skill_md.py tests/miles_portal/tenant/skills/test_skill_md.py
git mv tests/tenant/skills/test_skill_run_script.py tests/miles_portal/tenant/skills/test_skill_run_script.py
git mv tests/tenant/skills/test_skill_runtime_integration.py tests/miles_portal/tenant/skills/test_skill_runtime_integration.py
git mv tests/tenant/system/test_user_service.py tests/miles_portal/tenant/system/test_user_service.py
git mv tests/tenant/tools/test_agent_executor.py tests/miles_portal/tenant/tools/test_agent_executor.py
git mv tests/tenant/tools/test_compliance_check_text.py tests/miles_portal/tenant/tools/test_compliance_check_text.py
git mv tests/tenant/tools/test_flow_invoker_session.py tests/miles_portal/tenant/tools/test_flow_invoker_session.py
git mv tests/tenant/tools/test_invoke_custom_script.py tests/miles_portal/tenant/tools/test_invoke_custom_script.py
git mv tests/tenant/tools/test_invoke_tool_with_context.py tests/miles_portal/tenant/tools/test_invoke_tool_with_context.py
git mv tests/tenant/tools/test_run_flow_once.py tests/miles_portal/tenant/tools/test_run_flow_once.py
git mv tests/tenant/tools/test_tools_catalog.py tests/miles_portal/tenant/tools/test_tools_catalog.py
git mv tests/tenant/tools/test_tools_confirmation.py tests/miles_portal/tenant/tools/test_tools_confirmation.py
git mv tests/tenant/tools/test_tools_invoke.py tests/miles_portal/tenant/tools/test_tools_invoke.py
git mv tests/tenant/tools/test_tools_parameters.py tests/miles_portal/tenant/tools/test_tools_parameters.py
```

- [ ] **Step 2: 确认只有重命名**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git status --porcelain | grep -v '^R ' ; git status --porcelain | wc -l
```

Expected: 第一条无输出；第二条为 `99`（98 个 `test_*.py` + 辅助模块 `_usage_doubles.py`）。

> `tests/tenant/models/_usage_doubles.py` 是被两个用例 `import` 的共享辅助模块（非 `test_*.py`），
> 必须与用例同批搬走，否则 `from tests.tenant.models._usage_doubles import ...` 立刻断掉。

- [ ] **Step 2b: 改写 `_usage_doubles` 的导入路径（2 处）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "from tests\.tenant\.models\._usage_doubles" tests
```

预期命中 2 处，均为同一行内容：

- `tests/miles_portal/tenant/models/test_chat_usage_accumulation.py:15`
- `tests/miles_portal/tenant/models/test_chat_usage_sink_session.py:21`

两处都由

```python
from tests.tenant.models._usage_doubles import _cm, _ShortSession
```

改为

```python
from tests.miles_portal.tenant.models._usage_doubles import _cm, _ShortSession
```

（`tests/` 下无 `__init__.py`，靠 PEP 420 命名空间包解析；标准入口 `python -m pytest` 已把 `backend/` 放进 `sys.path`，与现状同机制。）

- [ ] **Step 3: 按域拆分 `test_p1_features.py`**

创建 `tests/miles_portal/tenant/tasks/test_task_batch_cancel.py`：

```python
"""任务批量取消请求体：``task_ids`` 原样保留（P1 能力冒烟）。"""

from miles_portal.tenant.tasks.schemas.task import TaskBatchCancelBody


def test_task_batch_cancel_body():
    body = TaskBatchCancelBody(task_ids=["a", "b"])
    assert len(body.task_ids) == 2
```

创建 `tests/miles_portal/tenant/generative/test_generative_batch_cancel.py`：

```python
"""生成任务批量取消请求体：``job_ids`` 原样保留（P1 能力冒烟）。"""

from uuid import uuid4

from miles_portal.tenant.generative.schemas.job import GenerativeJobBatchCancelBody


def test_generative_batch_cancel_body():
    body = GenerativeJobBatchCancelBody(job_ids=[uuid4()])
    assert len(body.job_ids) == 1
```

删除原文件（用例已分别落到两个域，文件本身不再需要）：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git rm tests/api/test_p1_features.py
```

- [ ] **Step 4: 跑该批目标目录**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/miles_portal
```

Expected: `767 passed`（拆分后两个文件各 1 个用例，与原文件 2 个用例等价）

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
refactor(tests): 测试目录按包搬迁第四批（miles_portal）

tenant/*、marketplace、deletion 全部归到 miles_portal；agents 域里的 A2A 出站用例
纠偏到 a2a 域、kb 域里的附件用例纠偏到 attachments 域；并拆掉唯一一个横跨两域的
test_p1_features.py（tasks / generative 各一个文件）。
MSG
```

---

### Task 5: 搬迁 `miles_admin` 与守卫上移（10 个文件）

**Files:**
- Modify（重命名）：见 Step 1

**Interfaces:**
- Consumes: Task 4 的提交
- Produces: `tests/miles_admin/{app_ops,app_sys,models}/`、根级 `tests/test_domain_meta.py`、`tests/test_api_enum_parity.py`、`tests/test_enum_contract.py`、`tests/test_orm_registry_completeness.py`、`tests/integration/test_module_smoke.py`

- [ ] **Step 1: 建目录并重命名（根级 4 个 AST 守卫与 `integration/test_integration_pipeline.py` 原地不动，不要写 no-op 的 `git mv`）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_admin/app_ops tests/miles_admin/app_sys tests/miles_admin/models
git mv tests/admin/test_admin_admins.py tests/miles_admin/app_ops/test_admin_admins.py
git mv tests/admin/test_admin_auth.py tests/miles_admin/app_sys/test_admin_auth.py
git mv tests/admin/test_admin_billing_plan.py tests/miles_admin/app_ops/test_admin_billing_plan.py
git mv tests/admin/test_admin_risk_enforce.py tests/miles_admin/app_ops/test_admin_risk_enforce.py
git mv tests/admin/test_audit_log_indexes.py tests/miles_admin/models/test_audit_log_indexes.py
git mv tests/api/test_domain_meta.py tests/test_domain_meta.py
git mv tests/api/test_module_smoke.py tests/integration/test_module_smoke.py
git mv tests/models/test_api_enum_parity.py tests/test_api_enum_parity.py
git mv tests/models/test_enum_contract.py tests/test_enum_contract.py
git mv tests/models/test_orm_registry_completeness.py tests/test_orm_registry_completeness.py
```

- [ ] **Step 2: 把 `test_api_enum_parity.py` 的路径推导改走 `tests.paths`**

原文（`tests/test_api_enum_parity.py` 第 133–134 行）：

```python
_BACKEND = Path(__file__).resolve().parents[2]
_PACKAGES = _BACKEND / "packages"
```

替换为：

```python
_BACKEND = BACKEND_ROOT
_PACKAGES = PACKAGES
```

并在 import 区的第一方分组里加（与 `from miles_*` 同组，不加空行）：

```python
from tests.paths import BACKEND_ROOT, PACKAGES
```

（该文件已上移到 `tests/` 根，`parents[2]` 原本会指到 `backend/` 的上一层；改常量后与位置无关。该文件的 `Path` 在下面 `_scan_declaration_files()` 等处仍大量使用，故 `from pathlib import Path` 保留不动。）

- [ ] **Step 3: 跑该批目标目录（含根级守卫与 integration）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/miles_admin tests/test_domain_meta.py tests/test_api_enum_parity.py \
  tests/test_enum_contract.py tests/test_orm_registry_completeness.py tests/integration
```

Expected: `114 passed`（该批搬迁的 10 个文件 110 个用例 + `tests/integration/test_integration_pipeline.py` 的 4 个用例；根级 4 个 AST 守卫的 16 个用例留到 Task 8 全量一起跑）

- [ ] **Step 4: 检查根级树形态**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
ls -1 tests | grep -v '^__pycache__$' | LC_ALL=C sort
```

Expected（此步 `tests/test_tests_layout.py` 尚未创建；`LC_ALL=C` 下 `README.md` 排最前）：

```text
README.md
conftest.py
integration
miles_admin
miles_ai
miles_common
miles_core
miles_exec
miles_openapi
miles_portal
miles_server
miles_worker
paths.py
test_api_enum_parity.py
test_domain_meta.py
test_enum_contract.py
test_l3_neutral_imports.py
test_no_blocking_calls_in_async.py
test_no_silent_broad_except.py
test_no_unreferenced_modules.py
test_orm_registry_completeness.py
```

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
refactor(tests): 测试目录按包搬迁第五批（miles_admin 与跨包守卫上移）

运营后台用例归入 miles_admin；跨包/跨域契约守卫（domain_meta、api_enum_parity、
enum_contract、orm_registry_completeness）与跨包 import 冒烟上移到 tests/ 根与
integration/，并让 api_enum_parity 的路径推导走 tests.paths 常量。
MSG
```

---

### Task 6: 新增结构守卫 `tests/test_tests_layout.py`

**Files:**
- Modify: `tests/paths.py`
- Create: `tests/test_tests_layout.py`

**Interfaces:**
- Consumes: Task 5 的提交
- Produces: `tests.paths.TESTS_ROOT`（`Path`，指向 `backend/tests`）

- [ ] **Step 1: 在 `tests/paths.py` 增加 `TESTS_ROOT`**

原文（`tests/paths.py` 全文）：

```python
"""测试用路径常量（子目录内勿用 ``Path(__file__).parents[1]`` 猜 backend 根）。"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = BACKEND_ROOT / "packages"
MILES_AI = PACKAGES / "miles-ai" / "src" / "miles_ai"
MILES_SERVER = PACKAGES / "miles-server" / "src" / "miles_server"
```

替换为：

```python
"""测试用路径常量（子目录内勿用 ``Path(__file__).parents[N]`` 猜 backend 根）。

目录深度随「按包镜像」的层级变化，``parents[N]`` 会静默指错，故一律用本模块常量。
"""

from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_ROOT.parent
PACKAGES = BACKEND_ROOT / "packages"
MILES_AI = PACKAGES / "miles-ai" / "src" / "miles_ai"
MILES_SERVER = PACKAGES / "miles-server" / "src" / "miles_server"
```

- [ ] **Step 2: 写结构守卫（这是新增的守卫代码，完整落盘）**

创建 `tests/test_tests_layout.py`：

```python
"""tests 目录结构守卫：一级目录 = 被测包；用例归属包前缀自洽；文件基名唯一。

背景：2026-09-21 把 ``tests/`` 由「单包时代的域目录」重构为按 ``packages/`` 镜像
（一级目录 = 被测包，深层 = 包内模块层）。三条判据把该结构固化成契约：

1. ``tests/`` 一级只能是被测包目录、``integration/`` 与根级守卫/基础设施文件；
2. ``tests/miles_<pkg>/**`` 下的用例至少 import 一次该包（宽松口径：只判包前缀，
   不判到具体目录，跨域用例仍可存在）；
3. 全仓 ``test_*.py`` 基名唯一——``tests/`` 无 ``__init__.py``，pytest 的 ``prepend``
   导入模式要求基名唯一，否则报 import file mismatch。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.paths import TESTS_ROOT

# 允许的一级目录：被测包 + 跨包集成
_ALLOWED_TOP_LEVEL = frozenset(
    {
        "integration",
        "miles_common",
        "miles_exec",
        "miles_core",
        "miles_ai",
        "miles_portal",
        "miles_admin",
        "miles_openapi",
        "miles_server",
        "miles_worker",
        "miles_runner",  # 当前无直接用例（能力经 miles_exec 覆盖），保留以便新增用例时无需改守卫
    }
)

# 根级允许的非测试文件（README.md 是目录说明，随守卫一起保留）
_ALLOWED_ROOT_FILES = frozenset({"conftest.py", "paths.py", "README.md"})

# 例外登记：以路径读取被测源码做文本断言，无 import。新增例外须写明理由。
_PATH_ONLY_EXEMPTIONS = frozenset({"miles_server/scripts/seed/test_model_catalog_seed.py"})


def _iter_tests() -> list[Path]:
    """全仓测试文件（排序后返回，排除 __pycache__）。"""
    return sorted(p for p in TESTS_ROOT.rglob("test_*.py") if "__pycache__" not in p.parts)


def test_top_level_dirs_are_package_or_integration():
    """``tests/`` 一级只允许被测包目录与 ``integration/``，根级只允许守卫与基础设施文件。"""
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.iterdir()):
        if path.name == "__pycache__":
            continue
        if path.is_file():
            if path.name in _ALLOWED_ROOT_FILES or path.name.startswith("test_"):
                continue
            offenders.append(path.name)
            continue
        if path.name not in _ALLOWED_TOP_LEVEL:
            offenders.append(f"{path.name}/")
    assert not offenders, "tests/ 一级出现未登记的目录/文件：\n" + "\n".join(offenders)


def test_package_prefixed_tests_import_their_package():
    """``tests/miles_<pkg>/**`` 下的用例至少要 import 一次该包（拦住包归属漂移）。"""
    offenders: list[str] = []
    for path in _iter_tests():
        rel = path.relative_to(TESTS_ROOT)
        pkg = rel.parts[0]
        if not pkg.startswith("miles_") or len(rel.parts) < 2:
            continue
        if rel.as_posix() in _PATH_ONLY_EXEMPTIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(rf"^\s*(?:from|import)\s+{pkg}\b", text, re.MULTILINE) is None:
            offenders.append(rel.as_posix())
    assert not offenders, "以下用例未 import 其目录对应的包（放错包目录）：\n" + "\n".join(offenders)


def test_test_file_basenames_are_unique():
    """全仓 ``test_*.py`` 基名唯一——无 ``__init__.py`` 时 pytest 的硬约束。"""
    by_name: dict[str, list[str]] = {}
    for path in _iter_tests():
        by_name.setdefault(path.name, []).append(path.relative_to(TESTS_ROOT).as_posix())
    dupes = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    assert not dupes, "测试文件基名重复（pytest 会报 import file mismatch）：\n" + "\n".join(
        f"{name}: {paths}" for name, paths in sorted(dupes.items())
    )
```

- [ ] **Step 3: 跑守卫**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/test_tests_layout.py
```

Expected: `3 passed`

- [ ] **Step 4: 验证守卫有判别力（临时造违例，必须红）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/legacy_domain
.venv/bin/python -m pytest -q tests/test_tests_layout.py
```

Expected: FAIL，报错含 `tests/ 一级出现未登记的目录/文件：` 与 `legacy_domain/`

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rmdir tests/legacy_domain
.venv/bin/python -m pytest -q tests/test_tests_layout.py
```

Expected: `3 passed`

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests
git commit -F - <<'MSG'
test(tests): 新增测试目录结构守卫并把路径常量收进 tests.paths

结构一旦漂移就静默退化成 grep 找用例，故把三条判据固化：一级目录白名单、
miles_<pkg> 用例的包前缀自洽、测试文件基名唯一（无 __init__.py 时 pytest 的硬约束）。
MSG
```

---

### Task 7: 同步文档与旧路径引用

**Files:**
- Modify: `backend/tests/README.md`
- Modify: `docs/architecture/layering.md:381-398`
- Modify: `backend/README.md:8-14`
- Modify: 7 处测试 docstring 里的旧路径
- Modify: `backend/pyproject.toml`、`docs/guides/*.md`、`docs/architecture/*.md` 与 `backend/packages/**` 注释里约 25 处旧测试路径（Step 5 按表替换）

**Interfaces:**
- Consumes: Task 6 的提交
- Produces: 文档中的目录树与守卫清单与磁盘一致

- [ ] **Step 1: 重写 `backend/tests/README.md`**

全文替换为：

````markdown
# 后端测试目录

与 [packages/](../packages/) 的包边界对齐：**一级目录 = 被测包**，深层 = 该包内的模块目录；
用例文件的位置 ⇔ 被测模块的位置（`miles_runner` 当前无直接用例，能力经 `miles_exec` 覆盖，故无对应目录）。归属规则与逐文件映射见
[docs/superpowers/specs/2026-09-21-tests-structure-design.md](../../docs/superpowers/specs/2026-09-21-tests-structure-design.md)。

```text
tests/
  conftest.py          # 全局 fixture（api_app、api_client 等）
  paths.py             # 路径常量（勿在子目录内猜 backend 根，用 TESTS_ROOT/BACKEND_ROOT/PACKAGES）
  test_l3_neutral_imports.py          # AST 守卫：L3 反向依赖 / server 自建 router
  test_no_blocking_calls_in_async.py  # AST 守卫：async 内不得直调阻塞调用
  test_no_silent_broad_except.py      # AST 守卫：宽泛 except / suppress 不得静默
  test_no_unreferenced_modules.py     # AST 守卫：不得出现零引用模块
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
````

- [ ] **Step 2: 更新 `docs/architecture/layering.md` §7 的目录树**

把 §7「测试布局」代码块（testpaths/守卫/file 列表）替换为：

````markdown
## 7. 测试布局

```text
backend/tests/                     # 一级目录 = 被测包（与 packages/ 对齐；miles_runner 无直接用例）
  conftest.py  paths.py
  test_l3_neutral_imports.py       # AST 守卫：L3 反向依赖 / server 自建 router
  test_no_blocking_calls_in_async.py
  test_no_silent_broad_except.py
  test_no_unreferenced_modules.py
  test_domain_meta.py  test_api_enum_parity.py  test_enum_contract.py
  test_orm_registry_completeness.py  test_tests_layout.py
  integration/                     # 跨包编排
  miles_common/ miles_exec/ miles_core/ miles_ai/ miles_portal/
  miles_admin/ miles_openapi/ miles_server/ miles_worker/
```

单测 `rag` 模块时 **不启动** FastAPI；向量库测试 mock `get_vector_store`。
归属规则与逐文件映射见
[docs/superpowers/specs/2026-09-21-tests-structure-design.md](.../superpowers/specs/2026-09-21-tests-structure-design.md)；
运行方式见 [tests/README.md](../../backend/tests/README.md)。
````

- [ ] **Step 3: 更新 `backend/README.md` 目录结构表**

把该行：

```text
├── tests/                   # 单一测试套件
```

替换为：

```text
├── tests/                   # 单一测试套件（一级目录 = 被测包，见 tests/README.md）
```

- [ ] **Step 4: 修正 7 处 docstring / 注释里的旧路径**

（`test_canvas_state_contract.py:20` 的 `tests/infra/<this>` 注释已在 Task 3 Step 2 连同 `parents[2]` 一起删掉，此处不再重复。）

| 文件 | 原文 | 改为 |
|---|---|---|
| `tests/test_no_silent_broad_except.py:7` | ``tests/rag/test_parse_degradation_diagnosability.py`` | ``tests/miles_ai/rag/test_parse_degradation_diagnosability.py`` |
| `tests/miles_openapi/views/test_a2a_server_api.py:3` | ``tests/tenant/a2a/test_a2a_server_card.py`` | ``tests/miles_portal/tenant/a2a/test_a2a_server_card.py`` |
| `tests/miles_portal/tenant/a2a/test_a2a_task_resubscribe.py:3` | ``tests/tenant/generative/test_generative_job_watch.py`` | ``tests/miles_portal/tenant/generative/test_generative_job_watch.py`` |
| `tests/miles_portal/tenant/agents/test_agent_chat_ws.py:226` | `tests/tenant/agents/test_agent_chat_ws.py` | `tests/miles_portal/tenant/agents/test_agent_chat_ws.py` |
| `tests/miles_portal/tenant/agents/test_chat_rag_connection_release.py:4` | `tests/rag/test_generate_rag_answer.py` | `tests/miles_ai/rag/test_generate_rag_answer.py` |
| `tests/miles_core/infra/db/test_db_pool_settings.py:20` | `tests/infra/test_loop_aware_engine.py` | `tests/miles_core/infra/db/test_loop_aware_engine.py` |
| `tests/miles_core/infra/db/test_loop_aware_engine.py:318` | ``tests/infra/test_infra.py`` | ``tests/miles_portal/tenant/system/test_infra.py`` |

核对方式（Task 2/3 已改掉的 2 处不再出现在结果里；`tests/README.md` 也在 Step 1 整篇重写、不含旧路径）：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "tests/(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)/" tests --glob '!**/__pycache__/**'
```

Expected: 无输出

- [ ] **Step 5: 同步活引用（文档 + `packages/` 注释里的测试路径）**

历史记录不改：`docs/superpowers/specs/**` 与 `.superpowers/**` 是当时的实施留档，路径保持原样（同 alembic 版本脚本的冻结口径）。下面这些是**活引用**，按表替换。

先枚举（排除历史留档）：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n --hidden "tests/(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)/" \
   backend docs .github Makefile --glob '!**/__pycache__/**' --glob '!docs/superpowers/**' --glob '!.superpowers/**' --glob '!.git/**'
```

替换映射（一律只改路径文字，**不改任何代码逻辑**）：

| 旧路径 | 新路径 |
|---|---|
| `tests/models/test_api_enum_parity.py` | `tests/test_api_enum_parity.py` |
| `tests/test_orm_registry_completeness.py` | `tests/test_orm_registry_completeness.py` |
| `tests/models/test_enum_contract.py` | `tests/test_enum_contract.py` |
| `tests/infra/test_canvas_state_contract.py` | `tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py` |
| `tests/infra/test_celery_task_names.py` | `tests/miles_worker/test_celery_task_names.py` |
| `tests/rag/test_upload_policy_alignment.py` | `tests/miles_ai/rag/test_upload_policy_alignment.py` |
| `tests/rag/test_parse_degradation_diagnosability.py` | `tests/miles_ai/rag/test_parse_degradation_diagnosability.py` |
| `tests/tenant/tools/test_toolkit_contract.py` | `tests/miles_ai/integrations/langchain/test_toolkit_contract.py` |
| `tests/tenant/agents/test_agent_chat_rag_flow_context.py` | `tests/miles_portal/tenant/agents/test_agent_chat_rag_flow_context.py` |
| `tests/tenant/{domain}/` | `tests/miles_portal/tenant/{domain}/` |
| `backend/tests/admin/` | `backend/tests/miles_admin/` |

已知命中文件（执行时以上面的 `rg` 输出为准，逐条替换）：

- `backend/pyproject.toml`（`test_enum_contract.py` 注释）
- `backend/README.md`（`test_orm_registry_completeness.py`）
- `backend/packages/miles-common/src/miles_common/schemas/{marketplace,api_enums}.py`
- `backend/packages/miles-admin/src/miles_admin/app_ops/schemas/enums.py`
- `backend/packages/miles-portal/src/miles_portal/tenant/*/schemas/enums.py`（11 个域）
- `backend/packages/miles-server/src/miles_server/registry.py`
- `backend/packages/miles-ai/src/miles_ai/integrations/langgraph/compiler/state.py`
- `backend/packages/miles-ai/src/miles_ai/rag/parse/upload_policy.py`
- `backend/packages/miles-core/src/miles_core/jobs/tasks.py`
- `docs/guides/{knowledge-base,ai-stack}.md`
- `docs/architecture/{layering,admin-ops-design,backend-reference-framework,engine-di-convergence}.md`

不改（历史留档）：`docs/superpowers/specs/**`、`.superpowers/**`。

> **实施期修正**：原计划把 `backend/tools/rename_to_workspace.py`（一次性 codemod，文件内已注明
> 「已完成使命，勿再重跑」）也列入「不改」，但它与 Step 6 的「全仓无输出」互斥。用户裁定**两者都做**：
> 该文件注释里指路的 `tests/infra/test_celery_task_names.py`、`tests/tenant/tools` 已一并更正为
> 迁移后的路径（只动注释文字，工具行为未动），使 Step 6 的核验严格为空。

> 这些改动全部落在注释与文档字符串里的路径文字上，不触碰任何表达式；`tests/` 侧的文件仅改 docstring，`packages/` 侧仅改 `#` 注释与模块 docstring（后者会进 OpenAPI 描述，若某个 docstring 被改动需执行 `make openapi-write` —— 本步只改**注释行**，故预期 `make openapi-check` 仍为 OK；若 Step 7 的门禁报快照差异，则说明误改了 docstring，回退该处改为 `#` 注释）。

- [ ] **Step 6: 全仓核对无残留旧路径**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n "tests/(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)/" \
   backend docs .github Makefile --glob '!**/__pycache__/**' --glob '!docs/superpowers/**' --glob '!.superpowers/**'
```

Expected: 无输出

- [ ] **Step 7: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A backend/tests/README.md backend/README.md backend/pyproject.toml docs/architecture docs/guides backend/packages backend/tests
git commit -F - <<'MSG'
docs(tests): 同步测试目录树与旧路径引用

tests/README.md、layering.md §7、backend/README.md 的目录说明按新结构重写；
测试 docstring、packages 注释与活文档里指向旧测试路径的引用一并更正，
避免读者按图索骥找不到文件（历史 spec 与一次性 codemod 留档不改）。
MSG
```

---

### Task 8: 收尾验证

**Files:**
- 无改动（只读验证）

**Interfaces:**
- Consumes: Task 7 的提交、Task 0 的快照
- Produces: 迁移完成的证据（命令输出）

- [ ] **Step 1: 用例集合逐条一致**

首先跑一遍结构守卫，拿到它新增的用例名（3 个），再与基线比对——除了这 3 个名字，其余必须逐条一致：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/tests-names-after.txt
wc -l /tmp/tests-names-after.txt
diff /tmp/tests-names-before.txt /tmp/tests-names-after.txt
```

Expected: `1517 /tmp/tests-names-after.txt`（1513 基线 + Task 6 新增 4 个守卫用例）；`diff` 输出**只有** 4 行 `>`，即：

```text
> test_package_prefixed_tests_import_their_package
> test_package_subdirs_mirror_source_modules
> test_test_file_basenames_are_unique
> test_top_level_dirs_are_package_or_integration
```

一行 `<` 都不能有（出现即说明有用例丢失或改名）。`test_p1_features.py` 拆成两文件后函数名不变，故不出现在 diff 里。

- [ ] **Step 2: 全量测试**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q
```

Expected: `1517 passed`

- [ ] **Step 3: 无硬编码深度残留**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "parents\[" tests
```

Expected: 只出现说明性命中——`tests/paths.py:1,3` 的 docstring（解释「勿用 `parents[N]` 猜 backend 根」）与
`tests/miles_core/infra/db/test_loop_aware_engine.py:274` 的注释（说明为何不再用深度推导）；
`tests/test_l3_neutral_imports.py:18` 的 `_PKG = Path(__file__).resolve().parents[1] / "packages"` 是该文件
**留在 `tests/` 根**时的正确推导（`parents[1]` 即 `backend/`），不在本次改造范围，允许保留。
除上述两类外不得出现其余命中——尤其不得出现「子目录内靠 `parents[N]` 猜 backend 根」的代码。

- [ ] **Step 3b: 旧测试路径引用已归零（文档）+ 跨用例导入已归零（代码）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n --hidden "tests/(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)/" \
   backend docs .github Makefile --glob '!**/__pycache__/**' --glob '!docs/superpowers/**' --glob '!.superpowers/**' --glob '!.git/**'
cd backend && rg -n "from tests\.(infra|flow|rag|media|mcp|models|tenant|admin|worker|api|marketplace)" tests
```

Expected: 两条命令均无输出

> `--hidden` 不可省：`rg` 默认跳过点文件，`backend/.importlinter` 里就藏着一处旧路径
> （`tests/models/test_api_enum_parity.py`），初版命令漏扫过它。

- [ ] **Step 3c: OpenAPI 快照未漂移（Task 7 若误改 DTO docstring 会在此暴露）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
python -m miles_server.scripts.export_openapi --check
```

Expected: OK（无差异）

- [ ] **Step 4: 目录形态复核**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
find tests -name "__pycache__" -prune -o -type d -print | sort
git status --porcelain
```

Expected: 目录集合与设计文档 §3 的目标树一致（`tests`、`tests/integration`、9 个 `tests/miles_*` 及其子目录）；`git status --porcelain` 为空

- [ ] **Step 5: 质量门禁（复刻 CI 后端 job）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make check
```

`make check` = `lint-backend`（ruff check）+ `format-check-backend`（ruff format --check）+ `layers-check`（import-linter）+ `openapi-check` + `test-backend`（全量 pytest）。

Expected: 五步均退出码 0、`1517 passed`。本计划只搬路径、新增一个守卫文件，未动 `packages/` 源码与 `.importlinter`；若 `ruff check` 报 I001（导入顺序），说明 `from tests.paths import …` 放错了分组——按同目录既有文件（如 `tests/test_orm_registry_completeness.py`）把 `tests.paths` 与 `miles_*` 放同一组、不加空行。

- [ ] **Step 6（可选）: 让 CI 跑一次**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git push
gh run watch
```

Expected: `lint.yml` 的 pytest 步骤通过（与本地一致）

---

## 自检清单（计划作者用）

- 规格覆盖：§2 归属规则 → Task 1–5 的逐文件命令；§4.1 分批 → Task 1–5；§4.2 拆分 → Task 4 Step 3；
  §4.3 `parents[N]` → Task 2 Step 2/3、Task 3 Step 2、Task 5 Step 2；§4.4 守卫 → Task 6；
  §4.5 文档与活引用 → Task 7；§4.6 验证口径 → Task 8。
- 附带改动已登记：跨用例 import 2 组（`_usage_doubles` → Task 4 Step 2b、`test_litellm_adapter` → Task 3 Step 2b）、
  共享辅助模块 `_usage_doubles.py` 随批搬迁（Task 4 Step 1）。
- 已实测核对（2026-09-21）：分批用例数 105/78/433/765+2/110+4、目标基名无冲突、包前缀守卫违规恰好 1 处且已登记豁免、
  跨用例导入恰好 4 处、`git mv` 干跑无缺目录/无覆盖、守卫代码通过 `ruff check` 与 `ruff format --check`。
- 无占位符：每个搬迁步骤都给出完整命令；每处内容改动都给出改前/改后代码。
- 类型一致：`TESTS_ROOT` / `BACKEND_ROOT` / `PACKAGES` 在 Task 6 定义，Task 2/3/5 与 Task 6 一致使用同名常量。

---

## 实施期修正（执行时发现，计划已按此回填）

| # | 计划原文 | 实际执行 | 原因 |
|---|---|---|---|
| 1 | Task 2/3 的「改后」注释写 `` `parents[N]` `` | 写 `` `parents` `` | 与 Task 3 Step 4 / Task 8 Step 3 的 `rg "parents\["` 验收互斥：写全会让验收命中该注释 |
| 2 | Task 8 Step 3 预期「只剩 `paths.py:1` 一行」 | 允许两类说明性命中（`paths.py:1,3` docstring、`test_loop_aware_engine.py:274` 注释）+ `test_l3_neutral_imports.py:18` 的根级 `parents[1]` | 前者是解释为何不再用深度推导；后者留在 `tests/` 根时 `parents[1]` 即 `backend/`，本就正确，不在改造范围 |
| 3 | Task 4 只搬 98 个文件 | 99 个（+ `tests/tenant/models/_usage_doubles.py`） | 该共享辅助模块被两个用例 import，不与用例同批搬走会立刻断链 |
| 4 | 未提跨用例 import | Task 3 Step 2b / Task 4 Step 2b 新增 4 处导入路径改写 | 同上：`tests.infra.test_litellm_adapter` 2 处、`tests.tenant.models._usage_doubles` 2 处 |
| 5 | Task 5 预期 `130 passed` | `114 passed` | 130 把根级 4 个 AST 守卫的 16 个用例也算进了该批命令，但那些文件不在命令的参数里 |
| 6 | Task 8 预期 `1513 passed` | `1517 passed` | 未计入 Task 6 新增的守卫用例（初版 3 条，终审后加固为 4 条）；比对方式改为「`diff` 只允许 4 行 `>` 新增」 |
| 7 | Task 6 的 `_ALLOWED_ROOT_FILES` 只有 `conftest.py`/`paths.py` | 加 `README.md` | 否则守卫在 `tests/` 根见到 `README.md` 就会红 |
| 8 | Task 7 Step 5 把 `backend/tools/rename_to_workspace.py` 列入「不改」，Step 6 又要求全仓无输出 | 两者都做（用户裁定）：改该文件 2 处注释，验收严格为空 | 前后两条互斥 |
| 9 | Task 7 Step 2 的 `layering.md` 链接写成 `(.../superpowers/...)` | `(../superpowers/specs/2026-09-21-tests-structure-design.md)` | 占位式写法从 `docs/architecture/` 解析不到 |
| 10 | 未提旧域空目录残留 | Task 5 同批 `rm -rf` 掉 11 个只剩 `__pycache__` 的旧域目录 | 搬完后它们未跟踪、内容已空，留着会污染目录形态复核 |
| 11 | Task 6 由实现者提交 | 实现者子代理在提交前被中断；改动已落盘且达标，由控制器完成验证与提交 | 见 `.superpowers/sdd/task-6-report.md`；未重做任何实现工作 |
| 12 | 文档写「与 packages/ 的包边界一一对应」 | 改为「对齐」并注明 `miles_runner` 无直接用例 | packages 有 10 个包，`tests/` 只有 9 个目录 |
| 13 | Task 3 把 `test_flow_multimodal.py` 归 `tests/miles_portal/tenant/flows/` | 改归 `tests/miles_ai/flow_runtime/` | 终审以设计 §2 R1 复核：8 个用例里 6 个（含全部 `patch` 目标）打 `miles_ai.flow_runtime`，只有 2 个碰 portal 的 `FlowRunRequest`；同类混合用例 `test_media_nodes.py` 早已按此裁定 |
| 14 | 结构性守卫只判「一级目录 + 包前缀」 | Task 6 后追加第 4 条判据 `test_package_subdirs_mirror_source_modules` + `_iter_tests()` 扫描面哨兵（下界 200） | 终审实测：把用例 `git mv` 进 `tests/miles_portal/totally_fake_domain/` 或搬到根级，守卫均为 `3 passed` —— 核心约定「深层 = 包内模块」当时并未被守 |
| 15 | Task 7 Step 6 的 `rg` 门禁未带 `--hidden` | 补 `--hidden`（+ `--glob '!.git/**'`），并修正 `backend/.importlinter:107` 的过期引用 | `rg` 默认跳过点文件，`.importlinter` 因而漏扫；账本原先「旧路径引用已归零」的断言严格来说不成立 |
| 16 | `docs/architecture/admin-ops-design.md` §5 只写到包级目录 | 补到模块级（3 个在 `app_ops/`、1 个在 `app_sys/`、1 个在 `models/`） | 原文把 5 个文件写成 `miles_admin/` 的直接子文件，读者 grep 会失败 |

## 执行结果（2026-09-21，分支 `refactor/tests-by-package`）

- 迁移前后用例集合逐条一致：1513（基线）→ 1517（+ Task 6 的 4 个守卫用例），`diff` 无 `<` 行。
- 全量 `1517 passed`；`make check` 五门全绿（ruff check / format --check / `Contracts: 7 kept, 0 broken.` / `OpenAPI snapshot OK` / pytest）。
- 全仓旧测试路径引用归零（`backend`、`docs`、`.github`、`Makefile`，排除历史 spec/plan 与 `.superpowers`）。
- 目录形态：`tests/` = 9 个包目录 + `integration/` + 根级守卫/基础设施文件，旧域目录已全部清除。
