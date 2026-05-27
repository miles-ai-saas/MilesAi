# 平台内智能体与内部协同

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块4 智能体管理  
**架构：** [technical-design.md §10](../architecture/technical-design.md#10-智能体对话) · [platform-agents.md](../guides/platform-agents.md)

---

## 1. 背景与目标

**平台内智能体**（`agent_type=custom`）绑定模型、知识库、工具、流程、技能包，通过 `POST …/chat` 进入统一编排。支持 **内部协同**：同租户多个 custom 智能体由父智能体委派子任务（DeepAgents 或平台 JSON 规划）。

**≠ A2A**：内部协同走 `agt_sub_agent_bindings`，子节点为本平台智能体，见 [a2a-interconnect.md](./a2a-interconnect.md)。

### 1.1 交付范围

- 智能体 CRUD、架构预览、统计、标签/分类
- 对话路由：A2A 宿主 / 内部协同 / 外部 Peer 增强 / 画布流程 / LangGraph RAG / 直连 LLM / tool_agent
- DeepAgents 可选依赖 + 平台规划降级
- 技能包注入、MCP/工具 function calling
- 对话工作台、架构拓扑图、执行时间线
- WebSocket / HTTP 双通道，见 [agent-chat-websocket.md](./agent-chat-websocket.md)

### 1.2 明确不做

- 对外暴露本平台 Agent Card（A2A Server 待做）
- 子智能体再绑子智能体（子节点须为叶子）

---

## 2. 数据模型

| 表/字段 | 说明 |
|---------|------|
| `agt_agents` | `agent_type`: `custom` \| `a2a`；`config` JSONB；`published_flow_id` |
| `agt_sub_agent_bindings` | 父→子：`role_hint`、`sort_order` |
| `agt_kb_bindings` | 智能体 ↔ KB M:N |
| `agt_agent_a2a_peer_refs` | custom 引用外部 Peer（见 a2a 文档） |

**内部协同约束：** 同租户、无自绑/成环、最多 8 个子智能体、子节点为叶子。

有绑定时自动：`runtime_mode=autonomous`、`planner=deepagents`。

---

## 3. 对话路由决策

```
POST /agents/{id}/chat
    → BEFORE_CALL 钩子 + check_input 合规
    → agent_type == a2a ? run_a2a_host_chat
    → 有 sub_agent_bindings ? run_subagent_planned_chat
        → (可选) augment_response_with_a2a
    → 仅有 peer_refs ? run_a2a_augmented_chat
    → published_flow_id ? flow_runtime.run
    → 绑 KB + use_langgraph_rag ? run_rag_workflow
    → enable_tool_calling / 生图工具 ? tool_agent
    → rag_answer / ainvoke_chat
    → check_output + AFTER_CALL
```

| 路径 | 条件 |
|------|------|
| 内部协同 | `agt_sub_agent_bindings` 非空 |
| 画布流程 | `published_flow_id` + 已发布版本 |
| RAG Graph | 绑 KB、`use_langgraph_rag` 未关 |
| tool_agent | `enable_tool_calling` 或 KB+生图工具等 |

---

## 4. 内部协同执行

1. **DeepAgents**（已装 `[agent-stack]` 且主智能体有模型）：`create_deep_agent` + `CompiledSubAgent`，`chat_as_child`
2. **降级**：异常或未安装 → 平台 JSON 规划 + 顺序/并行 `chat_as_child`
3. **强制平台**：`config.force_platform_planner: true`

| `config` 键 | 默认 | 说明 |
|-------------|------|------|
| `max_plan_iterations` | 12 | DeepAgents recursion_limit |
| `max_subagent_calls` | 20 | 平台规划上限 |
| `subagent_parallel` | false | 平台规划并行 |
| `skill_package_id` | — | SKILL.md 注入 |
| `enable_tool_calling` | false | LiteLLM tools 循环 |
| `carry_forward_media` | false | 多轮识图沿用附图 |

`steps` 类型：`planner`、`subagent_dispatch`、`subagent`、`planner_fallback`。

`conversation_id`：DeepAgents 用 `deep:{id}` 前缀，与 RAG checkpoint 隔离。

---

## 5. API

前缀：`/api/v1/agents`  
权限：`agent:read` · `agent:write`

```
GET  /agents/meta
GET  /agents?agent_type=&category_id=&tag_ids=
POST /agents
GET/PATCH/DELETE /agents/{id}
GET  /agents/{id}/stats
GET  /agents/{id}/architecture      # 拓扑与主路径预览
POST /agents/{id}/chat
WS   /agents/{id}/chat/ws
…/schedules                         # 见 agent-schedules.md
```

---

## 6. 前端

| 路径/组件 | 功能 |
|-----------|------|
| `/workbench/agents` | 列表 Tab：全部 / 智能体 / A2A |
| `/workbench/agents/chat` | 对话工作台 |
| `AgentFormDialog` | 创建/编辑向导（含 KB、内部协同、A2A 引用） |
| `AgentArchitecturePanel` | 架构图 |
| `AgentExecutionTimeline` | steps 时间线 |

---

## 7. 后端文件清单

```
backend/app/models/agent.py
backend/app/tenant/agents/services/agent/
backend/app/tenant/agents/views/agents.py
backend/app/integrations/deepagents/
backend/app/integrations/langgraph/runner.py
backend/app/tenant/a2a/invoke.py          # augment / host
```

---

## 8. 测试计划

1. 无 KB 直连 chat → answer
2. 绑 KB → RAG 命中 citations
3. 绑 2 个子 agent → steps 含 subagent
4. 绑 published_flow → 流程输出
5. `pip install -e ".[agent-stack]"` 后 DeepAgents 路径

---

## 9. 参考

- [platform-agents.md](../guides/platform-agents.md)
- [ai-stack.md](../guides/ai-stack.md)
- [a2a-interconnect.md](./a2a-interconnect.md)
- [flow-orchestration.md](./flow-orchestration.md)
- [skill-packages.md](../guides/skill-packages.md)
