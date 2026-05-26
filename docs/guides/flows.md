# 流程编排（flow_runtime + LangGraph）

> 类型：流程编排 | 状态：已实现 | 关联：[technical-design.md](../architecture/technical-design.md) §9

画布 `graph_json` **仅由 LangGraph 编译执行**；`flow_runtime` 提供节点 handler，编译与执行在 `integrations.langgraph`。

## 命名与数据流

| 名称 | 路径 |
|------|------|
| flow_runtime | `backend/app/flow_runtime/` |
| LangGraph 编译/执行 | `backend/app/integrations/langgraph/` |
| 前端画布 | `@xyflow/react` |

```
React Flow → PUT /flows/{id}/graph → flow_versions
调试/智能体 → get_flow_runtime().run() → LangGraph → nodes/registry
```

## 节点与扩展

支持类型：`TextInput`、`ChatInput`、`KnowledgeSearch`、`ConditionBranch`、`ParallelJoin`、`PromptTemplate`、`LLMCall`、`TextOutput`、`ChatOutput`。

扩展：在 `nodes/registry.py` 注册，并在 `frontend/lib/flow-nodes.ts` 增加调色板。

`POST /flows/{id}/compile` 预览编译结果；不可编译返回 `400` + `errors`。要求 **DAG**（无环）。

### 内置 RAG 画布模板

线性模板（无 `ConditionBranch`）：`TextInput → KnowledgeSearch → PromptTemplate → LLMCall → TextOutput`。

| 位置 | 说明 |
|------|------|
| 后端 JSON | [`flow_runtime/templates/rag_flow.json`](../backend/app/flow_runtime/templates/rag_flow.json) |
| 结构说明 | [`templates/README.md`](../backend/app/flow_runtime/templates/README.md) |
| 前端初始化 | `frontend/lib/flow-nodes.ts` → `RAG_TEMPLATE` |
| 市场种子 | `tenant.marketplace.util.load_rag_graph_template()` |

编译执行见 `integrations.langgraph.compiler`（`build_canvas_graph` / `run_compiled_canvas`），**不同于**下文 Agent LangGraph RAG 图。

### ConditionBranch（`data.mode`）

| mode | 说明 |
|------|------|
| `has_hits` | 检索 hits 非空 |
| `score_above` | 最高分 ≥ threshold（默认 0.35） |
| `text_contains` | 文本含 keyword |
| `not_empty` | 上游文本非空 |

出边 `sourceHandle`：`true` / `false`。

### ParallelJoin（`data.merge_strategy`）

`dict`（默认）| `concat_text` | `first`。多入边亦可扇入汇合。

## 枚举元数据

`GET /flows/meta`（注册在 `/flows/{id}` 之前）返回列表/筛选用的 `statuses`（`draft` / `published` 等 `value` + `label`），与 `GET /hooks/meta` 同模式。前端 `flows/page.tsx` 进入时 `api.getFlowMeta()`，状态标签用 `optionLabel(meta.statuses, status)`。

## 与智能体

| 场景 | 路径 |
|------|------|
| `published_flow_id` | LangGraph 画布 |
| 仅知识库 | LangGraph RAG 或 `legacy` 线性 RAG（见 [ai-stack.md](./ai-stack.md)） |
| 子智能体绑定 | DeepAgents（见 [platform-agents.md](./platform-agents.md)） |

## LangGraph RAG 对话

未绑流程、已绑知识库时，默认 `run_rag_workflow()`：

```mermaid
flowchart TD
    START --> retrieve[检索 Weaviate]
    retrieve --> grade[评估相关性]
    grade -->|无结果| fallback[兜底]
    grade -->|低分可重试| retry[扩大 top_k]
    grade -->|可接受| generate[生成]
    retry --> retrieve
    generate --> END
    fallback --> END
```

| `Agent.config` | 默认 | 说明 |
|----------------|------|------|
| `use_langgraph_rag` | true | 关闭则线性 `rag_answer` |
| `runtime_mode` | — | `legacy` 强制线性 RAG |
| `relevance_threshold` | 0.35 | 低分重试/兜底阈值 |
| `rag_max_retries` | 1 | 重试时 top_k 翻倍（上限 20） |
| `use_llm_grade` | false | LLM 复核相关性 |

模块：`integrations/langgraph/graphs/rag_qa.py`、`runner.py`。合规/钩子仍在 `AgentService.chat` 外层。

### Checkpoint

`conversation_id` → `thread_id = {tenant_id}:{agent_id}:{conversation_id}`。需 **Redis Stack 或 Redis 8+**，`LANGGRAPH_REDIS_DB=0`；否则回退 `MemorySaver`（重启不保留状态）。依赖：`langgraph-checkpoint-redis`（见 `backend/.env.example`）。

## 历史

- 已移除内置 DAG 执行器（`BuiltinFlowRuntime`）及第三方流程产品适配层
- 已移除 `flow_flows.external_flow_id`（原外部流程 ID 预留列）
