# Engine DI：L3 对 L1 反依赖收敛（复盘）

> **状态**：已完成（2026-09-08 ~ 2026-09-10）。依赖规则以 [layering.md](./layering.md) §2.2 为准，本文回答三个问题：**为什么这么做 / 现在长什么样 / 新代码怎么接**。

## 1. 问题：L3 反向依赖 L1

分层方向是 `L0 → L1 → L2 → L3 → L4`，但 L3（`integrations/**`、`flow_runtime/**`）为了实现能力，最容易写成直接 import 用例层：

```python
# 反例：L3 直接拿 L1 的租户能力
from app.tenant.models.services.model_resolve import resolve_invoke_model
from app.tenant.tools.invoke import invoke_tool_with_context
from app.tenant.attachments.services.attachment import AttachmentService
```

后果：

| 后果 | 说明 |
|------|------|
| 依赖方向倒置 | L3 无法脱离业务被单测/复用；分层形同虚设 |
| 装配点分散 | 同一能力在多个 L3 文件里各自拼会话、构造 `TenantContext` |
| 循环引用 | L1 也 import L3（法向），于是只能靠函数级 import 绕过，隐蔽且易回归 |

收敛前的典型规模：模型解析、用量记录、KB 向量化/重排、工具 schema 与执行、合规词表、提示词模板、子流程图加载、媒体读取、生成编排（合规/配额/持久化/参考图）——散落在约 20 个 L3 文件里各自 import `app.tenant.*`。

## 2. 决策：契约下沉 + L1 装配注入

一句话：**能力实现留在 L1，L3 只依赖中立契约，由 L1 在装配点注入。**

三种注入形态，按「能力的生命周期」选：

| 形态 | 适用 | 契约位置 | 典型例子 |
|------|------|----------|----------|
| **A. 入参注入 + Protocol** | 调用链上一次性传入的能力/数据 | 跨层纯数据放 `app/models/**`；仅 L3 内部用的放 L3 包内 `io.py` / `*_contract.py` / `contracts.py` | `UsageSink`、`MediaReader`、`ToolExecutor`、`FlowRepoLike`、`CustomToolSpec`、`AgentServiceLike` |
| **B. `RunContext` 回调** | 画布运行时按节点动态需要、且需随流程透传的能力 | `flow_runtime/types.py` 字段声明 | `resolve_model`、`media_reader`、`load_subflow_graph` … |
| **C. 中立下沉** | 值/枚举/纯算法/纯函数，无 I/O | `app/models/**` | `models/agent/constants.py`、`models/agent/chat_io.py`、`models/tool/parameters.py`、`models/compliance/{pipeline,constants}.py`、`models/media/reader.py` |

放置判据：

- 是**纯数据/纯算法**吗？→ 下沉 `app/models/**`（L0~L3 都可 import）。
- 是**需要租户会话/DB 的实现**吗？→ 留 L1 `app/tenant/**`，对外只暴露函数或 `build_*` 工厂。
- 是**只有 L3 内部需要**的窄契约吗？→ 放 L3 包内（如 `integrations/deepagents/io.py`）。
- L1 侧原有 import 路径要保稳吗？→ 转 re-export shim（`# noqa: F401`），例如 `tenant/agents/schemas/agent.py`、`tenant/tools/parameters.py`。

**禁止**在 L3 留「反向 re-export shim」（`integrations/**` re-export `tenant/**`）——那是把反向依赖藏起来，且会被守卫测试直接判失败。

## 3. 收敛清单

各阶段收敛记录见 [layering.md](./layering.md) §8 修订记录；本文按阶段汇总成因与契约。

| 阶段 | 反依赖点 | 中立契约 | L1 实现/装配 | 形态 |
|------|----------|----------|--------------|------|
| B-1 | `integrations`/`flow_runtime` → `tenant.models.services.model_resolve` | `integrations/litellm/usage_sink.py::UsageSink` | `AgentService.resolve_invoke_model` / `chat_usage_sink`；`tenant/models/services/usage.py::ChatUsageSink` | A |
| B-1 | 同上（画布） | `RunContext.resolve_model` | `tenant/flows/services/run_context.py::make_flow_model_resolver` | B |
| B-2b | `langchain/{embeddings,visual_embeddings,vectorstores}`、`rag` → `embedding_resolve`/`rerank_resolve`/`search_log` | `integrations/langchain/kb_retrieval.py::KbRetrievalBindings` | `tenant/kb/services/embeddings.py::build_kb_retrieval_bindings` → `RunContext.kb_retrieval` | A+B |
| B-2c | `integrations/generative/*` → `model_resolve` | — | `tenant/models/services/generative_model_resolve.py`（`resolve_{image,video}_gen_model` 等）；`tenant/generative/services/job_execution.py` | A+B |
| B-2d | `integrations/deepagents/*`、`langgraph/runner` → `tenant.agents.{schemas,constants}` | `models/agent/constants.py`；`integrations/deepagents/io.py::{ParentChatInput,SubAgentPlanResult,AgentServiceLike}` | `AgentService.chat_as_child_simple`（`chat_entry.py`） | A+C |
| B-2e | `flow_runtime/nodes/{image,video}_generate` → `tenant.generative.{schemas.job,services.job}` | `RunContext.submit_generative_{image,video}` | `job_execution.py::submit_generative_{image,video}_job` | B |
| F2a | `langchain/tool_agent/{loop,artifacts}` → `tenant.agents.schemas.agent` | `models/agent/chat_io.py` | schemas 转 shim | C |
| F2b | `langchain/tools.py` 查 `Tool` 表 | `integrations/langchain/tools.py::CustomToolSpec`/`build_platform_tools`（纯构造）；`models/tool/parameters.py` | `tenant/tools/services/custom_tools.py::{load_custom_tool_specs,assemble_agent_tools}` → `loop(platform_tools=...)` | A+C |
| F2c-A | `flow_runtime/nodes/tool_nodes` → `tenant.tools.invoke` | `RunContext.invoke_platform_tool` | `tenant/tools/services/flow_invoker.py::build_flow_tool_invoker` | B |
| F2c-B | `tool_agent/loop` → `tenant.tools.{confirmation,invoke}` | `tool_agent/tool_contract.py::{ToolExecutor,ToolConfirmationSignal}` | `tenant/tools/services/agent_executor.py::build_agent_tool_executor` → `loop(tool_executor=...)` | A |
| G2-2 | `flow_runtime/nodes/rag_nodes` → `tenant.prompts.models` | `RunContext.resolve_prompt_template` | `tenant/prompts/services/template_loader.py::build_prompt_template_loader` | B |
| G2-3 | `flow_runtime/nodes/compliance_nodes` → `tenant.compliance.*`、`get_sync_db` | `models/compliance/{pipeline,constants}.py` | `tenant/compliance/services/scan_words_loader.py::build_scan_words_loader` → `RunContext.load_scan_words` | B+C |
| G2-1 | `flow_runtime/subflow/{resolve,validate}`、`nodes/{subflow,loop}_nodes` → `FlowRepository` | `flow_runtime/subflow/contracts.py::FlowRepoLike` | `tenant/flows/services/subflow_loader.py::build_subflow_graph_loader`；`FlowService` 传 `self.repo` | A+B |
| G2-4a | `flow_runtime/nodes/media_nodes` → `tenant.attachments.services.attachment` | `models/media/reader.py::{MediaReader,AttachmentBytes}` | `tenant/attachments/services/media_reader.py::build_flow_media_reader`（长会话） | B |
| G1-1 | 常量散落 L3 | `models/compliance/constants.py`、`integrations/generative/constants.py` | — | C |
| G1-2 | `integrations/generative/*` 含租户编排 | — | `tenant/generative/services/orchestration.py`（合规/配额/参考图/持久化/登记）；`persist.py` 同步下沉；`RunContext.generate_{image,video}_sync` | B |
| G1-3 | `integrations/chat/multimodal` → `AttachmentService` | 复用 `MediaReader` | `tenant/attachments/services/media_reader.py::build_session_media_reader`（复用调用方 `db`/`ctx`） | A |

**收官判据**：`integrations/**` 与 `flow_runtime/**` 对 `app.tenant` 引用为零（含 `TYPE_CHECKING` 与惰性 import）；`app/rag/**`（L2）同样为零。

## 4. `RunContext` 回调总览

画布节点拿到的是能力回调，而非模块。字段声明见 [`backend/app/flow_runtime/types.py`](../../backend/app/flow_runtime/types.py)：

| 字段 | 用途 | L1 提供方 | 未装配行为 |
|------|------|-----------|------------|
| `resolve_model` | LLM 节点按 `model_config_id` 解析（含 BYOK） | `flows/services/run_context.py::make_flow_model_resolver` | 节点报错 |
| `usage_sink_factory` | 画布 LLM 用量记录（按节点解析出的模型构造 sink） | `tenant/models/services/usage.py::make_flow_usage_sink_factory` | 未装配 ⇒ 该次调用不记录 |
| `kb_retrieval` | KB 向量化/重排/检索日志绑定 | `kb/services/embeddings.py::build_kb_retrieval_bindings` | `KnowledgeSearch` 节点报错 |
| `resolve_generative_image/video` | 生图/生视频模型解析 | `generative_model_resolve.py` | 同步分支报错 |
| `submit_generative_image/video` | 异步 job 提交 | `generative/services/job_execution.py` | `None` ⇒ 落同步 resolver 兜底 |
| `invoke_platform_tool` | `platform_tool` 节点执行 | `tools/services/flow_invoker.py::build_flow_tool_invoker` | 节点报错 |
| `resolve_prompt_template` | 提示词模板 live 引用 | `prompts/services/template_loader.py` | 引用模板时报错 |
| `load_scan_words` | 合规敏感词表 | `compliance/services/scan_words_loader.py` | 节点报错 |
| `load_subflow_graph` | SubFlow/LoopNode 子图加载 | `flows/services/subflow_loader.py` | 节点报错 |
| `media_reader` | 媒体节点读附件字节 | `attachments/services/media_reader.py::build_flow_media_reader` | OCR/ASR 节点报错 |
| `generate_image_sync/video_sync` | 同步生成编排 | `generative/services/orchestration.py::generate_{image,video}_for_model` | 同步分支报错 |

> `submit_generative_*` 按 `settings.generative_{image,video}_async` 门控注入或 `None`，该不变式由 `tests/tenant/agents/test_agent_chat_rag_flow_context.py` 固化。

## 5. 装配点与透传链

**两根 ROOT 装配点**（新建 `RunContext` 只能在这两处或其新增同族点）：

1. `app/tenant/agents/services/agent/chat_rag.py::flow_run_context` —— Agent 对话触发画布
2. `app/tenant/flows/services/flow.py`（debug-run，约 L265）—— 流程调试运行

**透传**（派生，不重新解析 L1 依赖）：

- LangGraph：`integrations/langgraph/compiler/run.py` 初始 state → `build.py::_State`/`run_node` 重建 `RunContext`
- 子流程：`flow_runtime/subflow/resolve.py::build_child_context`

**新增画布能力 checklist**：

1. `flow_runtime/types.py` 加回调字段 + docstring 说明签名与未装配行为；
2. 节点改为 `ctx.<回调>`，删掉 `app.tenant` import；
3. L1 写 `build_*` 工厂（内部可用 `AsyncSessionLocal` / `TenantContext`）；
4. **两处 ROOT 装配点都注入**，并把字段加入 LangGraph state 与 subflow 透传；
5. 未装配时报显式错误（`BadRequestError`），不要静默降级；
6. `tests/test_l3_neutral_imports.py` 若新增 L3 子包，登记扫描范围。

## 6. 守卫与 CI 门禁

守卫是**源码扫描**（不需要 DB/夹具），扫描 `integrations/**`、`flow_runtime/**` 全部 `.py`：

```text
backend/tests/test_l3_neutral_imports.py
禁止子串：app.tenant / from app import tenant / import app.tenant
```

已接入 CI（`.github/workflows/lint.yml` 的 backend job）：`L3 reverse-dependency guard` 独立成步，随后跑全量 `pytest`；同一 job 还跑 `ruff check` / `ruff format --check` / OpenAPI 快照。

## 7. 边界与取舍

- **`quota.py` 归位属内聚性，不是反依赖**：它本就无 `tenant` import，但内容是「租户配置 + 附件计数 + 调用前校验」，与 `integrations/generative/__init__.py` 声明的「本层不含配额」矛盾，故 2026-09-10 从 L3 迁至 `tenant/generative/services/quota.py`。判断标准是**职责归属**，不是「能否 import」。
- **L2 `rag/` 也需保持对 tenant 清零**：`rag → tenant` 在 §2.2 同样禁止；G1-3 顺带移除了 `rag_qa`/`rag_answer` 仅用于读图的会话与 `_tenant_from_state`。
- **缺装配不是降级理由**：RAG 有附图但 `media_reader` 为 `None` 时显式 `BadRequestError`（`rag_qa.generate/fallback`、`rag/generate/answer.py`），避免静默丢图。
- **画布用量已按模型记录**：`RunContext.usage_sink_factory(ModelConfig) -> UsageSink` 由 L1 `tenant/models/services/usage.py::make_flow_usage_sink_factory` 装配；LLM 节点解析出模型后构造 `FlowUsageSink`（`source="flow"`，`record` 自开短会话落 `ModelUsageLog` 并提交）。画布各节点可指定不同模型，故按模型逐次构造，避免归因到单一模型；未装配时该次调用不记录。
- **守卫是目录级覆盖**：`_CONVERGED` 直接登记 `integrations`、`flow_runtime` 两个目录，新增子包自动纳入扫描；只有出现新的**顶层 L3 目录**时才需要登记。

## 8. 相关文档

- 分层规则与逐条收敛记录：[layering.md](./layering.md)（§2.2 依赖规则、§8 修订记录）
- 实施记录（按阶段）：[layering.md](./layering.md) §8 修订记录
- 后端参考框架（新域四件套与横切模板）：[backend-reference-framework.md](./backend-reference-framework.md)
