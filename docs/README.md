# 文档

设计与运维说明；快速上手见仓库根目录 [README.md](../README.md)。

## 目录结构

```
docs/
├── README.md                 # 本索引
├── product/                  # 产品与需求
│   └── prd.md
├── architecture/             # 架构与技术方案
│   ├── technical-design.md
│   ├── layering.md           # 后端分层与代码规范
│   ├── rag-module-migration.md
│   ├── vector-database-selection.md
│   └── mcp-sandbox.md
├── frontend/                 # 前端
│   └── design.md
├── operations/               # 运维与部署
│   └── database-setup.md
└── guides/                   # 功能专题（实现说明）
    ├── flows.md
    ├── platform-agents.md
    ├── a2a.md
    ├── ai-stack.md
    ├── model-providers.md
    ├── knowledge-base.md
    ├── mcp.md
    └── skill-packages.md
```

---

## 产品 (`product/`)

| 文档 | 说明 |
|------|------|
| [prd.md](./product/prd.md) | 立项需求原文 + **模块6 实现对照**（只读参考） |

## 架构 (`architecture/`)

| 文档 | 说明 |
|------|------|
| [technical-design.md](./architecture/technical-design.md) | 架构、分层、库表、API、**对象/向量存储与配置策略（§6.5）**（**主文档**） |
| [layering.md](./architecture/layering.md) | 后端分层、`app/rag` 目录与入库/检索流水线、import 规范 |
| [rag-module-migration.md](./architecture/rag-module-migration.md) | RAG 模块迁移清单（已完成）与后续插件位 |
| [vector-database-selection.md](./architecture/vector-database-selection.md) | 向量数据库选型：pgvector / Weaviate / Milvus / Qdrant / OpenSearch / ES |
| [mcp-sandbox.md](./architecture/mcp-sandbox.md) | MCP STDIO / 平台执行：沙箱与 Runner 隔离方案 |

## 前端 (`frontend/`)

| 文档 | 说明 |
|------|------|
| [design.md](./frontend/design.md) | 设计规范：品牌色、组件类、Logo、布局、**弹窗/Sheet（§5.7）** |

## 运维 (`operations/`)

| 文档 | 说明 |
|------|------|
| [database-setup.md](./operations/database-setup.md) | PostgreSQL 建库、Alembic、种子数据 |

## 专题指南 (`guides/`)

| 文档 | 说明 |
|------|------|
| [flows.md](./guides/flows.md) | 流程编排、LangGraph 画布与 RAG 对话 |
| [platform-agents.md](./guides/platform-agents.md) | 平台内智能体、内部协同（DeepAgents） |
| [a2a.md](./guides/a2a.md) | A2A 外部登记、互联宿主、custom 引用 |
| [ai-stack.md](./guides/ai-stack.md) | LangChain / LangGraph / DeepAgents 模块与调用链 |
| [model-providers.md](./guides/model-providers.md) | 模型供应商：内置目录 + 租户自定义 |
| [knowledge-base.md](./guides/knowledge-base.md) | **知识库 RAG 主文档**：入库、支持格式、检索 hybrid、API |
| [mcp.md](./guides/mcp.md) | **MCP 服务**：注册、同步、HTTP/SSE invoke、连接安全 |
| [skill-packages.md](./guides/skill-packages.md) | **技能包**：SKILL.md、导入（本地/ZIP/Git）、分类、智能体注入 |

运维 Compose 与 **Worker / RAG 可选依赖** 见 [../docker/README.md](../docker/README.md)；后端 [../backend/README.md](../backend/README.md)。

---

## 概念速查

| UI | `agent_type` / 数据 | 文档 |
|----|---------------------|------|
| 智能体 Tab | `custom` | [platform-agents.md](./guides/platform-agents.md) |
| 内部协同 | `agt_sub_agent_bindings` | 同上 |
| A2A → 外部登记 | `agt_a2a_peers` | [a2a.md](./guides/a2a.md) |
| A2A → 互联宿主 | `a2a` | 同上 |
| 引用外部 | `agt_agent_a2a_peer_refs` | [a2a.md](./guides/a2a.md) §平台内引用 |

**内部协同 ≠ A2A**，分表、分 Tab、互不替代。

## 命名约定

画布编排：**React Flow** 编辑 `graph_json`，**flow_runtime** 注册节点，**integrations.langgraph** 编译执行。

## 代码入口

| 能力 | 路径 |
|------|------|
| 租户 API | `backend/app/tenant/` |
| 智能体对话 | `tenant/agents/services/agent.py` |
| A2A | `tenant/a2a/` |
| 流程 | `app/flow_runtime/`（节点、[templates/rag_flow.json](../backend/app/flow_runtime/templates/rag_flow.json)）、`app/integrations/langgraph/`（画布 compiler、Agent RAG 图） |
| RAG 入库 | `app/rag/pipeline/ingest.py` ← `tenant/kb/services/ingest.py` |
| RAG 能力 | `app/rag/`（parse / chunk / index / retrieve / generate / load） |
| 技能包 | `tenant/skills/`（存储 `storage.py`、导入 `import_service.py`） |
| AI 集成 | `app/integrations/langchain/`、`app/integrations/deepagents/` |

REST 以运行中 OpenAPI（`/docs`）为准。
