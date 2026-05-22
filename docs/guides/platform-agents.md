# 平台内智能体与内部协同

> 类型：智能体 | 状态：已实现 | 关联：[a2a.md](./a2a.md)（外部协议，语义不同）

## 产品语义

| 概念 | 说明 |
|------|------|
| **平台内智能体** | `agent_type=custom`（智能体 Tab）：模型、KB、工具、流程 |
| **内部协同** | `agt_sub_agent_bindings` 绑定同租户其他 custom，由 DeepAgents 或平台 JSON 规划委派 |
| **≠ A2A** | 子节点为本平台 `agt_agents`，不走 Agent Card |

UI：列表可显示 `内部协同 · N 子智能体`；配置在创建/编辑向导第 4 步「知识库与内部协同」。

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
cd backend && pip install -e ".[agent-stack]"   # deepagents、langgraph>=1.2
```

| `Agent.config` | 默认 | 说明 |
|----------------|------|------|
| `max_plan_iterations` | 12 | DeepAgents recursion_limit |
| `max_subagent_calls` | 20 | 平台规划上限 |
| `subagent_parallel` | false | 平台规划是否并行 |

`steps` 类型：`planner`、`subagent_dispatch`、`subagent`、`planner_fallback`。

模块：`app/integrations/deepagents/orchestrator.py`、`runner.py`、`subagent_graphs.py`。

`ChatRequest.conversation_id` 用于 DeepAgents `thread_id`（前缀 `deep:`，与 RAG checkpoint 隔离）。

## general-purpose 占位

DeepAgents 默认注入 `general-purpose` 子智能体；本平台用占位 `CompiledSubAgent` 引导改用已绑定 slug（如 `retrieval_a1b2c3d4`）。
