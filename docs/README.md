# 文档

设计与运维说明；快速上手见仓库根目录 [README.md](../README.md)。

## 文档分层（阅读顺序）

| 层级 | 路径 | 何时读 | 维护时机 |
|------|------|--------|----------|
| **需求基线** | `product/` | 了解立项背景与 PRD 差异 | 只读；差异写在 features / 产品文 |
| **功能规格** | `features/` |  onboarding、测试、API/表/文件清单 | **功能合入时同步** |
| **实现指南** | `guides/` | 排错、调用链、契约细节 | 行为/契约变更时 |
| **架构** | `architecture/` | 设计决策、目标架构、路线图 | 大改或归档时；**As-Is 以 features 为准** |
| **立项归档** | `superpowers/` | 历史 spec/plan，过程稿 | 不再更新，勿与现网混淆 |

推荐路径：**features → guides → architecture/technical-design.md**。

## 目录结构

```
docs/
├── README.md                 # 本索引
├── product/                  # 产品与需求
│   ├── prd.md
│   ├── backlog.md            # PRD ⬜ 项排期 backlog
│   └── multimodal-capabilities.md
├── architecture/             # 架构与技术方案
│   ├── technical-design.md
│   ├── admin-ops-design.md
│   ├── marketplace-review-design.md
│   └── …
├── frontend/                 # 前端设计规范（非应用源码；应用在仓库 ui/）
│   └── design.md
├── features/                 # 功能节点规格（按模块，已实现对照）
│   ├── admin-ops.md
│   ├── marketplace.md
│   └── …
├── operations/               # 运维与部署
├── superpowers/              # 立项过程稿
└── guides/                   # 功能专题（实现说明）

ui/                           # 前端应用源码（与 docs/ 并列，见仓库根目录）
├── workbench/                # 租户端：AI 工作台 + 业务中心 + 组织设置 :3000
└── admin/                    # 运营后台 :3001
```

---

## 产品 (`product/`)

| 文档 | 说明 |
|------|------|
| [prd.md](./product/prd.md) | 立项需求原文 + **文首实现对照**（锚点 `as-is-module-*`） |
| [backlog.md](./product/backlog.md) | PRD 差距项 **P0/P1/P2 排期 backlog**（源自对照表 ⬜） |
| [multimodal-capabilities.md](./product/multimodal-capabilities.md) | **多模态产品能力**：生文/识图/生图·视频/知识库入库、场景与发布节奏 |

## 架构 (`architecture/`)

| 文档 | 说明 |
|------|------|
| [technical-design.md](./architecture/technical-design.md) | 架构、分层、库表、API、**对象/向量存储与配置策略（§6.5）**（**主文档**，v2.1） |
| [backend-reference-framework.md](./architecture/backend-reference-framework.md) | **后端参考框架**：面向其他 LLM 的可复用骨架（分层、横切设施代码模板、业务域四件套、规范护栏、搭建 Checklist） |
| [layering.md](./architecture/layering.md) | 后端分层、import 规范；**单文件 ≥500 行须按子包拆分**（§5.4，细则见 [backend/README.md](../backend/README.md)） |
| [rag-module-migration.md](./architecture/rag-module-migration.md) | RAG 模块迁移清单（已完成）与后续插件位 |
| [vector-database-selection.md](./architecture/vector-database-selection.md) | 向量数据库选型：pgvector / Weaviate / Milvus / Qdrant / OpenSearch / ES |
| [mcp-sandbox.md](./architecture/mcp-sandbox.md) | MCP STDIO / 平台执行：沙箱与 Runner 隔离方案 |
| [tools-runtime.md](./architecture/tools-runtime.md) | **工具运行时**：内置 / HTTP / 脚本 / MCP 统一执行平面（目标架构） |
| [flow-orchestration-enhancement.md](./architecture/flow-orchestration-enhancement.md) | **流程编排增强**：属性面板、调试、RAG 节点（已实现） |
| [flow-subflow-design.md](./architecture/flow-subflow-design.md) | **子流程 SubFlow**（已实现） |
| [system-management-design.md](./architecture/system-management-design.md) | **系统管理增强**：RBAC/会话/配额/审计分期方案 |
| [business-center-design.md](./architecture/business-center-design.md) | **业务中心**：租户项目制交付（广告公司试点）；workbench 第三分区 |
| [admin-ops-design.md](./architecture/admin-ops-design.md) | **运营后台增强**：安全闭环/计费/风控生效/管理员治理 |
| [marketplace-review-design.md](./architecture/marketplace-review-design.md) | **应用市场审核**：SaaS 平台审 / 私有化租户审（`review_mode`） |
| [multimodal-roadmap.md](./architecture/multimodal-roadmap.md) | **多模态技术总览**：文档地图、附件无签名约定、实施顺序 |
| [realtime-transport-design.md](./architecture/realtime-transport-design.md) | **实时通道**：对话 WebSocket、生成任务 SSE、协议草案与分期 |
| [agent-multimodal-design.md](./architecture/agent-multimodal-design.md) | 智能体对话多模态（设计归档） |
| [flow-llm-multimodal-design.md](./architecture/flow-llm-multimodal-design.md) | 流程 `LLMCall` 识图输入（设计归档） |
| [flow-generative-media-design.md](./architecture/flow-generative-media-design.md) | 流程生图/生视频节点（设计归档） |
| [media-assets-design.md](./architecture/media-assets-design.md) | **生成物媒体资产**（设计归档 → [features/attachments-media-generative.md](./features/attachments-media-generative.md)） |

## 功能节点 (`features/`)

按 PRD 模块与横切能力拆分的**实现规格**（数据模型 · API · 调度 · 前后端清单 · 测试）。模板见 [agent-schedules.md](./features/agent-schedules.md)。

| 文档 | PRD 模块 | 说明 |
|------|----------|------|
| [platform-agents.md](./features/platform-agents.md) | 模块4 智能体 | 平台内智能体、内部协同、对话路由 |
| [a2a-interconnect.md](./features/a2a-interconnect.md) | 模块4 A2A | 外部登记、互联宿主、Peer 引用 |
| [agent-schedules.md](./features/agent-schedules.md) | 模块4 智能体 | 定时任务（Celery Beat） |
| [agent-chat-websocket.md](./features/agent-chat-websocket.md) | 模块4 智能体 | 对话 WebSocket v1 |
| [hooks.md](./features/hooks.md) | 模块2 钩子 | HTTP 切面扩展、Event v1 |
| [flow-orchestration.md](./features/flow-orchestration.md) | 模块4 编排 | React Flow + flow_runtime + LangGraph |
| [models-prompts.md](./features/models-prompts.md) | 模块3 模型/提示词 | 模型供应商 + 提示词模板 |
| [tools-mcp-skills.md](./features/tools-mcp-skills.md) | 模块5 工具生态 | 工具 / MCP / 技能包 |
| [kb-ingest-retrieval.md](./features/kb-ingest-retrieval.md) | 模块6 RAG | 知识库入库与检索 |
| [task-center.md](./features/task-center.md) | 模块8 异步任务 | 任务中心：入库 Celery + 生成任务 |
| [attachments-media-generative.md](./features/attachments-media-generative.md) | 模块4/6 多模态 | 附件、媒体资产、生图/生视频 |
| [tags-categories.md](./features/tags-categories.md) | 横切 | 租户标签 + 系统分类 |
| [marketplace.md](./features/marketplace.md) | 模块7 应用市场 | 打包、审核、安装、评分 |
| [system-management.md](./features/system-management.md) | 模块1 系统管理 | RBAC、用户、租户、配置、审计 |
| [business-center.md](./features/business-center.md) | 业务中心（租户） | 客户、项目、工作包、交付物；设计稿 |
| [compliance.md](./features/compliance.md) | 模块2 合规 | 敏感词库、扫描、拦截日志 |
| [monitor.md](./features/monitor.md) | 模块9 监控 | 统计、趋势、告警 Webhook |
| [admin-ops.md](./features/admin-ops.md) | 模块1 系统管理（平台侧） | 运营后台：租户、计费、风控、模型目录、分类 |

## 前端

| 应用 | 源码 | 设计规范 |
|------|------|----------|
| 租户工作台 | [ui/workbench/](../ui/workbench/) | [design.md](./frontend/design.md) |
| 运营后台 | [ui/admin/](../ui/admin/) | 同上（共用品牌与组件类） |

> 仓库根目录已无 `frontend/` 应用目录；`docs/frontend/` 仅存放设计规范文档。

## 运维 (`operations/`)

| 文档 | 说明 |
|------|------|
| [database-setup.md](./operations/database-setup.md) | PostgreSQL 建库、Alembic、种子数据 |
| [deployment.md](./operations/deployment.md) | Compose 全栈、Beat/Worker、Milvus 默认、mcp-runner |

## 专题指南 (`guides/`)

| 文档 | 说明 |
|------|------|
| [flows.md](./guides/flows.md) | 流程编排、LangGraph 画布与 RAG 对话 |
| [platform-agents.md](./guides/platform-agents.md) | 平台内智能体、内部协同（DeepAgents）、`GET /agents/meta` |
| [a2a.md](./guides/a2a.md) | A2A 外部登记、互联宿主、custom 引用 |
| [ai-stack.md](./guides/ai-stack.md) | LangChain / LangGraph / DeepAgents 模块与调用链 |
| [model-providers.md](./guides/model-providers.md) | 模型供应商：内置目录 + 租户自定义 |
| [model-config-extra.md](./guides/model-config-extra.md) | `ModelConfig.extra` / `invoke_mode` 常量对照 |
| [knowledge-base.md](./guides/knowledge-base.md) | **知识库 RAG 主文档**：入库、支持格式、检索 hybrid、API |
| [mcp.md](./guides/mcp.md) | **MCP 服务**：注册、同步、HTTP/SSE invoke、连接安全 |
| [tools.md](./guides/tools.md) | **工具**：内置 / HTTP / 变换脚本、API、与 MCP 关系（现网） |
| [skill-packages.md](./guides/skill-packages.md) | **技能包**：SKILL.md、导入（本地/ZIP/Git）、分类、智能体注入 |
| [compliance-word-libraries.md](./guides/compliance-word-libraries.md) | **合规敏感词库**：多库、扫描绑定、`GET /compliance/meta` |
| [hooks.md](./guides/hooks.md) | **智能体钩子**：切面扩展、Event v1、**全站 `/meta` 枚举字典约定** |

部署拓扑与 Celery 进程见 [operations/deployment.md](./operations/deployment.md)；Compose 细节与 **Worker / RAG 可选依赖** 见 [../docker/README.md](../docker/README.md)；后端 [../backend/README.md](../backend/README.md)。

## 立项归档 (`superpowers/`)

历史设计 spec 与实施 plan，**不作为现网规格**。入口：[superpowers/README.md](./superpowers/README.md)（清单与现网对照）。对照现网请读 `features/` 与同主题 `architecture/` / `guides/`。

| 文档 | 现网对照 |
|------|----------|
| [specs/2026-05-25-mcp-runner-sandbox-design.md](./superpowers/specs/2026-05-25-mcp-runner-sandbox-design.md) | [mcp-sandbox.md](./architecture/mcp-sandbox.md)、[features/tools-mcp-skills.md](./features/tools-mcp-skills.md) |
| [specs/2026-05-25-tools-design.md](./superpowers/specs/2026-05-25-tools-design.md) | [tools-runtime.md](./architecture/tools-runtime.md)、[guides/tools.md](./guides/tools.md) |
| [plans/2026-05-26-flow-orchestration-enhancement.md](./superpowers/plans/2026-05-26-flow-orchestration-enhancement.md) | [flow-orchestration-enhancement.md](./architecture/flow-orchestration-enhancement.md) |
| [plans/2026-05-26-flow-subflow.md](./superpowers/plans/2026-05-26-flow-subflow.md) | [flow-subflow-design.md](./architecture/flow-subflow-design.md)（暂不实施） |
| [plans/2026-05-25-tools-v1.md](./superpowers/plans/2026-05-25-tools-v1.md) | [features/tools-mcp-skills.md](./features/tools-mcp-skills.md) |

---

## 功能节点 ↔ 文档速查

| # | 功能节点 | 架构 | 指南 | features |
|---|----------|------|------|----------|
| 1 | 系统管理（租户） | [technical-design §4–5](./architecture/technical-design.md) | — | [system-management.md](./features/system-management.md) |
| 1b | 业务中心（租户） | [business-center-design.md](./architecture/business-center-design.md) | — | [business-center.md](./features/business-center.md) |
| 1a | 运营后台 | §4 运营域 | — | [admin-ops.md](./features/admin-ops.md) |
| 2 | 安全合规 | §11 | [compliance-word-libraries.md](./guides/compliance-word-libraries.md) | [compliance.md](./features/compliance.md)、[hooks.md](./features/hooks.md) |
| 3 | 模型与提示词 | §4 | [model-providers.md](./guides/model-providers.md) | [models-prompts.md](./features/models-prompts.md) |
| 4 | 智能体 / 内部协同 | §10 | [platform-agents.md](./guides/platform-agents.md) | [platform-agents.md](./features/platform-agents.md)、[agent-schedules.md](./features/agent-schedules.md)、[agent-chat-websocket.md](./features/agent-chat-websocket.md) |
| 4a | A2A 外部互联 | §10 | [a2a.md](./guides/a2a.md) | [a2a-interconnect.md](./features/a2a-interconnect.md) |
| 4b | 流程编排 | §9 | [flows.md](./guides/flows.md) | [flow-orchestration.md](./features/flow-orchestration.md) |
| 5 | 工具 / MCP / 技能 | §11 | [tools.md](./guides/tools.md)、[mcp.md](./guides/mcp.md)、[skill-packages.md](./guides/skill-packages.md) | [tools-mcp-skills.md](./features/tools-mcp-skills.md) |
| 6 | RAG 知识库 | §6 | [knowledge-base.md](./guides/knowledge-base.md) | [kb-ingest-retrieval.md](./features/kb-ingest-retrieval.md) |
| 6b | 附件 / 生成 / 素材 | §10.1 | — | [attachments-media-generative.md](./features/attachments-media-generative.md) |
| 7 | 应用市场 | §12 | — | [marketplace.md](./features/marketplace.md) |
| 8 | 异步任务 | §8 | — | [task-center.md](./features/task-center.md) |
| 9 | 监控统计 | §4 monitor | — | [monitor.md](./features/monitor.md) |
| — | 标签 / 分类 | §4 tags/categories | — | [tags-categories.md](./features/tags-categories.md) |
| — | 实时通道 | [realtime-transport-design.md](./architecture/realtime-transport-design.md) | — | [agent-chat-websocket.md](./features/agent-chat-websocket.md) |

## 概念速查

| UI | `agent_type` / 数据 | 文档 |
|----|---------------------|------|
| 智能体 Tab | `custom` | [platform-agents.md](./guides/platform-agents.md) · [features/platform-agents.md](./features/platform-agents.md) |
| 内部协同 | `agt_sub_agent_bindings` | 同上 |
| A2A → 外部登记 | `agt_a2a_peers` | [a2a.md](./guides/a2a.md) · [features/a2a-interconnect.md](./features/a2a-interconnect.md) |
| A2A → 互联宿主 | `a2a` | 同上 |
| 引用外部 | `agt_agent_a2a_peer_refs` | [a2a.md](./guides/a2a.md) §平台内引用 |

**内部协同 ≠ A2A**，分表、分 Tab、互不替代。

## 命名约定

画布编排：**React Flow** 编辑 `graph_json`，**flow_runtime** 注册节点，**integrations.langgraph** 编译执行。

## 代码入口

| 能力 | 路径 |
|------|------|
| 租户 API（AI + 组织） | `backend/app/tenant/` |
| 业务中心 API | `backend/app/biz/`（设计稿，`/api/v1/biz`） |
| 智能体对话 | `tenant/agents/services/agent.py` |
| A2A | `tenant/a2a/` |
| 流程 | `app/flow_runtime/`（节点、[templates/rag_flow.json](../backend/app/flow_runtime/templates/rag_flow.json)）、`app/integrations/langgraph/`（画布 compiler、Agent RAG 图） |
| RAG 入库 | `app/rag/pipeline/ingest.py` ← `tenant/kb/services/ingest.py` |
| RAG 能力 | `app/rag/`（parse / chunk / index / retrieve / generate / load） |
| 技能包 | `tenant/skills/`（存储 `storage.py`、导入 `import_service.py`） |
| 钩子 | `tenant/hooks/`（`HookRunner` / `HookExecutor`） |
| AI 集成 | `app/integrations/langchain/`、`app/integrations/deepagents/` |

REST 以运行中 OpenAPI（`/docs`）为准。
