# Engine DI：契约下沉与 RunContext 装配

> 依赖方向以 [layering.md](./layering.md) §2.2 为准。本文说明 L3（`integrations/**`、`flow_runtime/**`）如何只依赖中立契约、由 L1 在装配点注入能力，以及新增画布能力时的接法。

## 1. 原则

分层方向是 `L0 → L1 → L2 → L3 → L4`。**能力实现留在 L1**（`app/tenant/**`），**L3 只依赖中立契约**，由 L1 在装配点注入：

```python
# 反例：L3 直接 import L1 用例
from app.tenant.models.services.model_resolve import resolve_invoke_model
from app.tenant.tools.invoke import invoke_tool_with_context
```

直接把 L1 用例 import 进 L3 会导致依赖方向倒置（L3 无法脱离业务单测/复用）、装配点分散、以及只能靠函数级 import 绕过的循环引用。

**收官判据**：`integrations/**` 与 `flow_runtime/**` 对 `app.tenant` 引用为零（含 `TYPE_CHECKING` 与惰性 import）；L2 `app/rag/**` 同样为零。该判据由 §4 的源码扫描守卫固化。

## 2. 三种注入形态

按「能力的生命周期」选择：

| 形态 | 适用 | 契约位置 | 典型例子 |
|------|------|----------|----------|
| **A. 入参注入 + Protocol** | 调用链上一次性传入的能力/数据 | 跨层纯数据放 `app/models/**`；仅 L3 内部用的放 L3 包内 `io.py` / `*_contract.py` / `contracts.py` | `UsageSink`、`MediaReader`、`ToolExecutor`、`FlowRepoLike`、`CustomToolSpec`、`AgentServiceLike` |
| **B. `RunContext` 回调** | 画布运行时按节点动态需要、且需随流程透传的能力 | `flow_runtime/types.py` 字段声明 | `resolve_model`、`media_reader`、`load_subflow_graph` … |
| **C. 中立下沉** | 值/枚举/纯算法/纯函数，无 I/O | `app/models/**` | `models/agent/constants.py`、`models/agent/chat_io.py`、`models/tool/parameters.py`、`models/compliance/{pipeline,constants}.py`、`models/media/reader.py` |

放置判据：

- **纯数据 / 纯算法**？→ 下沉 `app/models/**`（L0~L3 都可 import）。
- **需要租户会话 / DB 的实现**？→ 留 L1 `app/tenant/**`，对外只暴露函数或 `build_*` 工厂。
- **只有 L3 内部需要的窄契约**？→ 放 L3 包内（如 `integrations/deepagents/io.py`）。
- **L1 侧原有 import 路径要保稳**？→ 转 re-export shim（`# noqa: F401`），例如 `tenant/agents/schemas/agent.py`、`tenant/tools/parameters.py`。

**禁止**在 L3 留「反向 re-export shim」（`integrations/**` re-export `tenant/**`）——那是把反向依赖藏起来，且会被守卫测试直接判失败。

## 3. `RunContext` 回调总览

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

## 4. 装配点与透传链

**两根 ROOT 装配点**（新建 `RunContext` 只能在这两处或其新增同族点）：

1. `app/tenant/agents/services/agent/chat_rag.py::flow_run_context` —— Agent 对话触发画布
2. `app/tenant/flows/services/flow.py`（debug-run）—— 流程调试运行

**透传**（派生，不重新解析 L1 依赖）：

- LangGraph：`integrations/langgraph/compiler/run.py` 初始 state → `build.py` 重建 `RunContext`
- 子流程：`flow_runtime/subflow/resolve.py::build_child_context`

**新增画布能力 checklist**：

1. `flow_runtime/types.py` 加回调字段 + docstring 说明签名与未装配行为；
2. 节点改为 `ctx.<回调>`，删掉 `app.tenant` import；
3. L1 写 `build_*` 工厂（内部可用 `AsyncSessionLocal` / `TenantContext`）；
4. **两处 ROOT 装配点都注入**，并把字段加入 LangGraph state 与 subflow 透传；
5. 未装配时报显式错误（`BadRequestError`），不要静默降级；
6. `tests/test_l3_neutral_imports.py` 若新增 L3 子包，登记扫描范围。

## 5. 守卫与 CI 门禁

守卫是**源码扫描**（不需要 DB/夹具），扫描 `integrations/**`、`flow_runtime/**` 全部 `.py`：

```text
backend/tests/test_l3_neutral_imports.py
禁止子串：app.tenant / from app import tenant / import app.tenant
```

已接入 CI（`.github/workflows/lint.yml` 的 backend job）：`L3 reverse-dependency guard` 独立成步，随后跑全量 `pytest`；同一 job 还跑 `ruff check` / `ruff format --check` / OpenAPI 快照。守卫为**目录级覆盖**：登记 `integrations`、`flow_runtime` 两个目录，新增子包自动纳入扫描，只有出现新的顶层 L3 目录时才需登记。

## 6. 边界与取舍

- **归位判据是职责归属**：某能力该留 L3 还是 L1，看它是否含租户配置、附件计数、DB 校验等业务职责，而非「能否 import」。例如生成日配额 `tenant/generative/services/quota.py` 虽无 `tenant` import，但含租户配置与调用前校验，归 L1。
- **L2 `rag/` 也须对 tenant 清零**：`rag → tenant` 在 layering §2.2 同样禁止。
- **缺装配不是降级理由**：RAG 有附图但 `media_reader` 为 `None` 时显式 `BadRequestError`，避免静默丢图。
- **画布用量按模型记录**：LLM 节点解析出模型后由 `usage_sink_factory(ModelConfig) -> UsageSink` 构造 `FlowUsageSink`（`source="flow"`，`record` 自开短会话落 `ModelUsageLog` 并提交）；画布各节点可指定不同模型，故按模型逐次构造，避免归因到单一模型。

## 7. 相关文档

- [layering.md](./layering.md) —— 分层规则（§2.2 依赖规则、§2.3 admin 访问租户域）
- [backend-reference-framework.md](./backend-reference-framework.md) —— 新域四件套与横切模板
