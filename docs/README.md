# 文档

设计与运维说明；快速上手见仓库根目录 [README.md](../README.md)。

## 文档列表

| 文档 | 说明 |
|------|------|
| [technical-design.md](./technical-design.md) | 架构、分层、库表、API 规范、分阶段计划（主文档） |
| [prd.md](./prd.md) | 立项需求原文（只读参考） |
| [database-setup.md](./database-setup.md) | PostgreSQL 建库、Alembic、种子数据 |
| [flows.md](./flows.md) | 流程编排、LangGraph 画布与 RAG 对话 |
| [platform-agents.md](./platform-agents.md) | 平台内智能体、内部协同（DeepAgents） |
| [a2a.md](./a2a.md) | A2A 外部登记、互联宿主、custom 引用 |
| [ai-stack.md](./ai-stack.md) | LangChain / LangGraph / DeepAgents 模块与调用链 |
| [model-providers.md](./model-providers.md) | 模型供应商：内置目录 + 自定义模型（规划） |

运维部署另见 [../docker/README.md](../docker/README.md)、[../backend/README.md](../backend/README.md)。

## 概念速查

| UI | `agent_type` / 数据 | 文档 |
|----|---------------------|------|
| 智能体 Tab | `custom` | [platform-agents.md](./platform-agents.md) |
| 内部协同 | `agt_sub_agent_bindings` | 同上 |
| A2A → 外部登记 | `agt_a2a_peers` | [a2a.md](./a2a.md) |
| A2A → 互联宿主 | `a2a` | 同上 |
| 引用外部 | `agt_agent_a2a_peer_refs` | [a2a.md](./a2a.md) §平台内引用 |

**内部协同 ≠ A2A**，分表、分 Tab、互不替代。

## 命名约定

需求中的「Langflow」= 本仓库 **React Flow + flow_runtime + LangGraph**，非 PyPI `langflow` 包。

## 代码入口

| 能力 | 路径 |
|------|------|
| 租户 API | `backend/app/app_tenant/` |
| 智能体对话 | `app_tenant/agents/services/agent.py` |
| A2A | `app_tenant/a2a/` |
| 流程 | `app/flow_runtime/`、`app/ai_stack/langgraph/` |
| AI 栈 | `app/ai_stack/langchain/`、`app/ai_stack/deepagents/` |

REST 以运行中 OpenAPI（`/docs`）为准。
