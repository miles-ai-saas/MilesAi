# DeepAgents 多子智能体协同

> 状态：已接入（`deepagents>=0.5` + 平台降级）

## 行为

主智能体绑定 ≥1 子智能体时，`POST /agents/{id}/chat` 走 `run_subagent_planned_chat`：

1. **优先 DeepAgents**（已安装 `deepagents` 且主智能体有模型）  
   - `create_deep_agent` + 各子智能体 `CompiledSubAgent`  
   - 子智能体 runnable 内部调用 `AgentService.chat_as_child`（保留 RAG/流程/直连能力）  
   - 主智能体通过 `task` 工具委派  
2. **降级**：DeepAgents 异常或未安装 → 平台 JSON 规划 + 顺序/并行 `chat_as_child`  
3. **强制平台规划**：`Agent.config.force_platform_planner: true`

## 配置（`Agent.config`）

| 字段 | 默认 | 说明 |
|------|------|------|
| `runtime_mode` | 绑子智能体时 `autonomous` | 自动写入 |
| `planner` | `deepagents` | 规划器 |
| `max_plan_iterations` | `12` | DeepAgents `recursion_limit` |
| `max_subagent_calls` | `20` | 平台规划路径上限 |
| `subagent_parallel` | `false` | 平台规划路径是否并行调用子智能体 |
| `force_platform_planner` | — | 跳过 DeepAgents |

## 依赖

```bash
cd backend
pip install -e ".[agent-stack]"   # 含 deepagents、langgraph>=1.2
```

`langgraph` 需 **≥1.2**（`deepagents` 依赖 `langgraph.prebuilt`）。

## 响应 `steps`

| type | 含义 |
|------|------|
| `planner` | `engine: deepagents` 或 `platform` |
| `subagent_dispatch` | DeepAgents 发起 task 委派 |
| `subagent` | 子智能体执行结果摘要 |
| `planner_fallback` | DeepAgents 失败转平台规划 |

## 模块

- `app/ai_stack/deepagents/orchestrator.py` — 入口与降级  
- `app/ai_stack/deepagents/runner.py` — `create_deep_agent`  
- `app/ai_stack/deepagents/subagent_graphs.py` — 子智能体 CompiledSubAgent  

## 会话

`ChatRequest.conversation_id` 用于 DeepAgents `thread_id` 后缀（与 RAG LangGraph checkpoint 隔离前缀 `deep:`）。

## general-purpose 工位

DeepAgents 默认会注入与主智能体等权的 `general-purpose` 子智能体。本平台在 `build_compiled_subagents` 中注入同名 **占位 CompiledSubAgent**，委派到该工位会提示改用已绑定的租户子智能体 slug（`task` 的 `subagent_type` 与 `CompiledSubAgent.name` 一致，如 `retrieval_a1b2c3d4`）。
