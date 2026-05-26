# 流程画布内置模板

## `rag_flow.json`

市场一键上架、种子数据与编译测试使用的 **最小 RAG 画布**（线性，无条件分支）。

### 节点与数据流

| 节点 id | 类型 | 说明 |
|---------|------|------|
| `input_1` | TextInput | 从 `RunContext.inputs["query"]` 读用户问题 |
| `search_1` | KnowledgeSearch | `retrieve_hits`；`data.top_k=5`；KB 来自节点 `kb_id` 或 `RunContext.kb_ids` |
| `prompt_1` | PromptTemplate | 占位符 `{{检索结果}}`、`{{用户提问}}` |
| `llm_1` | LLMCall | `ainvoke_chat`；模型来自 `RunContext.model_config_id` 或节点配置 |
| `output_1` | TextOutput | 流程终点 → `RunResult.output` |

### 边（handle）

- `input_1` → `search_1`：`query`
- `input_1` → `prompt_1`：`query`（问题同时进模板）
- `search_1` → `prompt_1`：`hits`（检索结果列表）
- `prompt_1` → `llm_1`：`prompt`
- `llm_1` → `output_1`：`input`

### 加载方式

- `flow_runtime.templates.registry` — 注册表与 `list_flow_templates()` / `load_flow_template_graph(id)`
- `GET /flows/templates` — 前端创建流程与编辑页「插入模板」
- `tenant.marketplace.util.load_rag_graph_template()` — 市场/种子兼容封装
- `backend/scripts/seed/marketplace.py`

### 与 Agent LangGraph RAG 的区别

本模板 **不** 经过 `integrations.langgraph.graphs.rag_qa`（无相关性评分/重试/兜底），
等价于「检索 → 拼 prompt → 单次 LLM」，与 `rag.generate.rag_answer` 类似。

### `rag_flow_with_grade.json`

带 **RelevanceGrade** 三路分支（good / poor / none）与 **StaticResponse** 兜底；与 Agent `rag_qa` 评分语义对齐（无 top_k 重试环）。

加载：`load_flow_template_graph("rag_grade")` 或 `load_rag_graph_template(variant="with_grade")`。

### 扩展建议

- 在 `search_1` 后增加 `ConditionBranch`（`mode=has_hits`）可做简单二分支
- 节点 `data.kb_id` 可写死单库；多库依赖 Agent 发布或 `FlowService.run(kb_ids=...)`
