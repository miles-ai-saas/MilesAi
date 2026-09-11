# 平台内智能体与内部协同

> 类型：智能体 | 状态：已实现  
> **功能规格：** [features/platform-agents.md](../features/platform-agents.md) · [features/agent-chat-websocket.md](../features/agent-chat-websocket.md)  
> 关联：[a2a.md](./a2a.md)（外部协议，语义不同）  
> **多模态（已实现）：** [multimodal-capabilities.md](../product/multimodal-capabilities.md)

## 产品语义

| 概念 | 说明 |
|------|------|
| **平台内智能体** | `agent_type=custom`（智能体 Tab）：模型、KB、工具、流程 |
| **内部协同** | `agt_sub_agent_bindings` 绑定同租户其他 custom，由 DeepAgents 或平台 JSON 规划委派 |
| **≠ A2A** | 子节点为本平台 `agt_agents`，不走 Agent Card |

UI：列表可显示 `内部协同 · N 子智能体`；配置在创建/编辑向导第 4 步「知识库与内部协同」。

## 枚举元数据

`GET /agents/meta`（注册在 `/agents/{id}` 之前）返回表单/列表用字典，与 `GET /hooks/meta` 同模式：

| 字段 | 说明 |
|------|------|
| `statuses` | `enabled` / `disabled` |
| `agent_types` | `custom` / `a2a` |
| `sub_agent_role_hints` | 子智能体 `role_hint`（含空值「未指定」） |
| `primary_paths` | 架构预览主路径（与 `AgentArchitectureOut` 一致） |

文案维护在 `backend/packages/miles-portal/src/miles_portal/tenant/agents/meta.py`；DeepAgents 子智能体描述与 `sub_agent_role_hints` 共用 `SUB_AGENT_ROLE_LABELS`。

## 数据与约束

- 表：`agt_sub_agent_bindings`（`parent_agent_id`, `child_agent_id`, `role_hint`, `sort_order`）
- 同租户、禁止自绑与成环、最多 8 个、子节点为叶子
- 有绑定时自动写入 `runtime_mode=autonomous`、`planner=deepagents`

## 执行路径

`POST /agents/{id}/chat` → `run_subagent_planned_chat`：

1. **DeepAgents**（已装 `deepagents` 且主智能体有模型）：`create_deep_agent` + `CompiledSubAgent`，子任务走 `chat_as_child`
2. **降级**：异常或未安装 → 平台 JSON 规划 + 顺序/并行 `chat_as_child`
3. **强制平台**：`force_platform_planner: true`

```bash
cd backend && uv sync --all-packages --group dev   # deepagents、langgraph>=1.2
```

### 对话实时通道

| 通道 | 状态 | 说明 |
|------|------|------|
| `POST /agents/{id}/chat` | ✅ | HTTP 整包返回；无 LLM 真 token 流式 |
| `WS …/chat/ws` | ✅ v1 | 会话级事件总线（delta 模拟、工具确认、job 进度）；见 [features/agent-chat-websocket.md](../features/agent-chat-websocket.md) |
| 生成任务 SSE | ✅ | `GET /generative/jobs/{id}/stream`；任务中心仍用 REST + SSE |
| LLM 真 token 流式 | 📋 | 见 [realtime-transport-design.md](../architecture/realtime-transport-design.md) |

| `Agent.config` | 默认 | 说明 |
|----------------|------|------|
| `max_plan_iterations` | 12 | DeepAgents recursion_limit |
| `max_subagent_calls` | 20 | 平台规划上限 |
| `subagent_parallel` | false | 平台规划是否并行 |

`steps` 类型：`planner`、`subagent_dispatch`、`subagent`、`planner_fallback`。

模块：`backend/packages/miles-ai/src/miles_ai/integrations/deepagents/orchestrator.py`、`runner.py`、`subagent_graphs.py`。

`ChatRequest.conversation_id` 用于 DeepAgents `thread_id`（前缀 `deep:`，与 RAG checkpoint 隔离）。

## general-purpose 占位

DeepAgents 默认注入 `general-purpose` 子智能体；本平台用占位 `CompiledSubAgent` 引导改用已绑定 slug（如 `retrieval_a1b2c3d4`）。

## 技能包与工具调用

智能体 `config` 可同时配置技能包与平台工具，二者职责不同：

| 配置项 | 作用 |
|--------|------|
| `skill_package_id` | 绑定单个技能包；`SKILL.md` 全文 + `references/scripts` **索引**注入 system prompt |
| `enable_tool_calling` | 开启 LiteLLM function calling 循环（`tool_agent`） |
| `tool_slugs` | 可选白名单；未配置时使用全部内置 + 租户自定义工具（MCP、绑定 KB 的 `knowledge_search` 不受其约束） |
| `mcp_service_ids` | 绑定 MCP 服务，其同步出的 tools 一并可 function calling |
| 知识库绑定 | 与 tool calling **共存**：`knowledge_search` 强制可用，命中片段回填 `sources` |

### 技能运行时工具

绑定 `skill_package_id` 且走 **无知识库** 的 tool calling 路径时，额外挂载：

| 工具 | 说明 |
|------|------|
| `skill_read_reference` | 按需读取 `references/`、`assets/` 文本 |
| `skill_run_script` | 沙箱执行 `scripts/*.py`（`run(params)`；默认需用户确认） |

工具自动使用当前智能体的 `skill_package_id`，LLM 无需传技能 ID。直接 `POST /tools/invoke` 时须带 `agent_id`（或参数中显式 `skill_package_id`）。

### 路径互斥说明

| 场景 | 技能 Prompt | skill_* 工具 |
|------|-------------|--------------|
| 无 KB + `enable_tool_calling` | ✅ | ✅ |
| 绑定 KB + `enable_tool_calling` | ✅ | ✅（`tool_agent` + `knowledge_search`） |
| 绑定 KB（未开工具调用） | ✅ | ❌（走 LangGraph / `rag_answer` 检索增强） |
| 仅 `_direct_chat` | ✅ | ❌ |

流程画布可使用 **PlatformTool** 节点（`data.tool_slug`）调用 `skill_read_reference` / `skill_run_script`；须由绑定技能包的智能体发布流程执行（注入 `agent_id`）。

详见 [skill-packages.md](./skill-packages.md)。
