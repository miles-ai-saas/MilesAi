# MilesAi 技术方案

> 版本：v2.2 | 与当前代码库对齐  
> 需求基线：[prd.md](../product/prd.md) · 专题文档：[README.md](../README.md)

本文描述**仓库已实现**的架构与行为；**功能规格**见 [features/](../features/)，专题见 [guides/](../guides/)。

---

## 目录

1. [概述](#1-概述)
2. [总体架构](#2-总体架构)
3. [仓库结构](#3-仓库结构)
4. [分层与模块](#4-分层与模块)
5. [多租户与权限](#5-多租户与权限)
6. [数据存储](#6-数据存储)
7. [API 概览](#7-api-概览)
8. [异步任务](#8-异步任务)
9. [流程编排](#9-流程编排)
10. [智能体对话](#10-智能体对话)
10.1. [多模态（已实现）](#101-多模态已实现)
11. [合规、钩子与工具](#11-合规钩子与工具)
12. [应用市场](#12-应用市场)
13. [前端](#13-前端)
14. [部署](#14-部署)
15. [配置与环境变量](#15-配置与环境变量)
16. [实施状态](#16-实施状态)

---

## 1. 概述

**MilesAi** 是企业级私有化 AI 中台：多租户工作台 + 运营后台，提供知识库 RAG、React Flow 流程编排、平台内智能体（含 DeepAgents 内部协同）、A2A 外部互联、合规与工具/MCP、应用市场。

### 1.1 设计原则（代码中的落地）

| 原则 | 实现 |
|------|------|
| 元数据与文件分离 | PostgreSQL 业务表；MinIO 对象；Weaviate 向量 |
| 租户隔离 | ORM 查询带 `tenant_id`；向量检索 Filter；删除编排 `deletion/` |
| 编排同进程 | `flow_runtime` 节点 + `integrations.langgraph` 编译执行 |
| 长任务异步 | 文档入库 `workers.tasks.ingest_document`（Celery 队列） |
| 双端 API | 租户 `/api/v1`；运营 `/api/admin/v1` |
| AI 栈可降级 | DeepAgents 未安装 → 平台 JSON 规划；MCP invoke 可为 mock |

### 1.2 与需求文档的差异

| 需求表述 | 当前实现 |
|----------|----------|
| 可视化流程编排 | **React Flow**（`@xyflow/react`）+ `graph_json` |
| 画布执行引擎 | **`flow_runtime` + LangGraph**（`get_flow_runtime` → 编译执行） |
| 独立 OCR/ASR 微服务 | 单 **worker** 容器，队列 `parse,ocr,asr,embed`（可选 multimodal 依赖） |

---

## 2. 总体架构

```mermaid
flowchart TB
    subgraph Clients
        WEB[租户工作台 :3000]
        ADM[运营后台 :3001]
    end

    subgraph API["FastAPI api :8000"]
        V1["/api/v1 租户"]
        ADM_API["/api/admin/v1 运营"]
    end

    subgraph BL["tenant 业务域"]
        AGT[agents / a2a]
        KB[kb]
        FLW[flows]
        CMP[compliance / hooks]
        MKT[marketplace]
        TOOL[tools / mcp / skills]
        ATT[attachments / media-assets / generative]
        TAG[tags / categories]
    end

    subgraph AI["integrations + rag + flow_runtime"]
        FR[flow_runtime 节点]
        LG[LangGraph 画布 / RAG]
        LC[LangChain 适配]
        DA[DeepAgents 可选]
    end

    subgraph Worker["Celery worker + Beat"]
        ING[ingest_document]
        GEN[generative image/video]
        SCH[tick_agent_schedules]
    end

    subgraph Store
        PG[(PostgreSQL)]
        RD[(Redis)]
        OBJ["对象存储<br/>S3 API · 默认 MinIO"]
        VEC["向量存储<br/>默认 Weaviate"]
    end

    WEB --> V1
    ADM --> ADM_API
    V1 --> BL
    BL --> AI
    BL --> PG
    BL --> RD
    BL --> OBJ
    BL --> VEC
    BL -->|enqueue| Worker
    Worker --> OBJ
    Worker --> VEC
    Worker --> PG
```

**启动顺序**（`apps/application.py` lifespan）：Alembic `upgrade head` → LangGraph checkpointer 初始化。种子数据由部署流程显式执行 `backend/cli.py init-db`（或 `cli.py seed <target>`），不在 API 启动时写入。日常开发/API/Worker 亦可通过 `cli.py serve` / `cli.py worker` 启动。

---

## 3. 仓库结构

```
MilesAi/
├── backend/
│   ├── app/
│   │   ├── main.py                 # uvicorn 入口
│   │   ├── apps/                   # FastAPI 工厂、路由汇总、启动迁移
│   │   ├── tenant/             # 租户 API（按域 views/services/models）
│   │   │   ├── agents/ a2a/ kb/ flows/ marketplace/ compliance/ …
│   │   │   └── router.py           # /api/v1
│   │   ├── admin/                  # 运营 API /api/admin/v1
│   │   ├── rag/                    # L2：parse / chunk / index / retrieve / generate / pipeline
│   │   ├── integrations/           # L3：langchain / langgraph / litellm / deepagents
│   │   ├── flow_runtime/           # 画布节点 registry、执行入口
│   │   ├── models/                 # 核心 ORM（Agent、Flow、KB、Task…）
│   │   ├── infra/                  # L4：db / redis / storage / vector_store 客户端
│   │   ├── core/                   # config、deps、security、tenant
│   │   ├── workers/                # Celery（ingest_document 等）
│   │   └── deletion/               # 级联删除
│   ├── alembic/versions/           # 001–009（见 §6.1）
│   └── pyproject.toml
├── ui/                             # 前端应用
│   ├── workbench/                  # 租户 Next.js 14
│   └── admin/                      # 运营 Next.js 14
├── docker/                         # infra + app compose
└── docs/                           # → docs/README.md
    ├── product/                    # 需求
    ├── architecture/               # 本文件
    ├── frontend/                   # 设计规范
    ├── operations/                 # 建库、迁移
    └── guides/                     # 流程、智能体、A2A、AI 栈…
```

---

## 4. 分层与模块

| 层 | 路径 | 职责 |
|----|------|------|
| 路由 | `tenant/*/views/` | 参数校验、依赖注入、调用 Service |
| 业务 | `tenant/*/services/` | 租户校验、编排、调用 `rag.*` / `integrations.*` |
| RAG | `rag/` | 解析、分片、索引门面、检索、生成、入库管道（见 [layering.md](./layering.md)） |
| 集成 | `integrations/` | LangChain Embedding/检索封装、LangGraph、LiteLLM |
| 仓储 | `tenant/*/repositories/`、`models/` | CRUD、分页 |
| 基础设施 | `infra/`、`core/`、`common/` | DB、Redis、对象存储、向量库客户端 |

**租户业务域**（均有独立 `router`）：

| 域 | 前缀 | 说明 |
|----|------|------|
| system | `/tenants` `/users` `/roles` `/system/configs` | 租户、用户、RBAC、配置 |
| categories | `/categories` | 系统预置资源分类（单选导航） |
| tags | `/tags` | 租户全局标签（多选、跨资源筛选） |
| kb | `/kb` | 知识库、文档、检索（详见 [knowledge-base.md](../guides/knowledge-base.md)） |
| attachments | `/attachments` | 会话/对话附件（非 KB 文档） |
| media-assets | `/media-assets` | 生成物媒体资产目录、升格 KB |
| generative | `/generative/jobs` | 生图/生视频异步任务、SSE 进度 |
| flows | `/flows` | 流程版本、画布、发布、运行、编译预览 |
| agents | `/agents` | 智能体 CRUD、`POST …/chat`、WebSocket、`…/schedules` |
| a2a | `/a2a/peers` | 外部 Peer 登记与 Card 同步 |
| models | `/models` | 大模型配置（内置 `tenant_id` 空 + 租户自定义；演进见 [model-providers.md](../guides/model-providers.md)） |
| compliance | `/compliance` | 敏感词库、扫描、拦截日志 |
| hooks | `/hooks` | Webhook 定义与绑定 |
| tools / mcp / skills | `/tools` `/mcp` `/skill-packages` | 工具目录、MCP、技能包 |
| prompts | `/prompt-templates` | 提示词模板 |
| marketplace | `/marketplace` | 应用打包、审核、安装、评分 |
| tasks | `/tasks` | Celery 任务记录查询（入库等） |
| workbench | `/workbench` | 工作台概览聚合统计 |
| monitor | `/monitor` | 统计、报表、告警配置 |
| audit | `/audit` | 租户操作审计 |

**运营域**（`admin/`，前缀 `/api/admin/v1`）：平台管理员认证、租户运营、计费、风控、审计。

---

## 5. 多租户与权限

- 登录：`POST /api/v1/auth/login` 签发 JWT；`TenantContext` 注入 `tenant_id`、`user_id`。
- 数据访问：Service 层 `assert_tenant_access` + 查询 `tenant_filters`。
- 权限：角色-权限表 `sys_roles` / `sys_permissions` / `role_permissions`；路由依赖 `require_permissions`。
- 软删除：多数业务表 `deleted_at`（迁移 `004`）；删除智能体/KB 等走 `deletion/cascade.py`。

默认种子（`backend/scripts/seed/`）：租户 `admin` / `admin123`；运营 `platform` / `admin123`（`scripts/seed/admin_ops.py`）。

---

## 6. 数据存储

### 6.1 PostgreSQL 核心表

迁移：`001_initial_schema`（`create_all` 建全库）+ `002`–`009` 增量（schedules、合规词库、media、generative 等）。

| 分组 | 表名 | 说明 |
|------|------|------|
| 系统 | `sys_tenants`, `sys_users`, `sys_roles`, `sys_permissions`, `sys_configs` | 租户与用户体系 |
| | `sys_categories` | 资源分类（系统预置） |
| | `sys_attachments` | 会话/对话附件元数据 |
| | `tnt_tags`, `tnt_entity_tag_bindings` | 租户标签与资源绑定 |
| 智能体 | `agt_agents` | `agent_type`: `custom` \| `a2a`；`config` JSONB |
| | `agt_model_configs` | 模型端点、加密 API Key |
| | `agt_model_tenant_credentials` | 租户 BYOK 凭证 |
| | `agt_sub_agent_bindings` | 平台内父子智能体 |
| | `agt_kb_bindings` | 智能体-知识库 M:N |
| | `agt_schedules` | 智能体定时任务（Cron + Beat） |
| A2A | `agt_a2a_peers` | 外部登记、Agent Card 缓存 |
| | `agt_a2a_peer_bindings` | 互联宿主 → peer（含 `trigger_keywords`） |
| | `agt_agent_a2a_peer_refs` | custom 智能体引用外部 peer |
| 流程 | `flow_flows`, `flow_versions` | `graph_json` |
| 知识库 | `kb_bases`, `kb_documents`, `kb_document_chunks`, `kb_vector_refs` | 文档状态与向量引用；**向量化规格绑在 `kb_bases`**（见 §6.5） |
| | `kb_search_logs` | 检索日志 |
| 多模态 | `media_assets` | 生成物媒体资产目录 |
| | `generative_jobs` | 生图/生视频异步任务 |
| 产品 | `prm_prompt_templates`, `skl_skill_packages`, `tool_tools`, `tool_mcp_services` | |
| | `tool_invocation_logs`, `mcp_runner_sessions` | 工具调用审计、MCP Runner 会话 |
| | `hook_definitions`, `hook_bindings`, `hook_execution_logs` | 钩子 |
| | `cmp_word_libraries`, `cmp_sensitive_word_entries`, `cmp_library_word_bindings`, `cmp_compliance_library_bindings`, `cmp_intercept_logs` | 合规词库与拦截 |
| | `mkt_categories`, `mkt_apps`, `mkt_ratings`, `mkt_installs` | 应用市场 |
| | `task_records`, `aud_logs` | Celery 任务记录、审计 |
| 运营 | `adm_admins`, `adm_billing_*`, `adm_risk_*`, `adm_audit_logs` | 仅运营 API 使用 |

ORM **不在库级声明外键**（`001` 使用 `create_all`）；关联由应用层维护。

### 6.2 对象存储（S3 兼容）

**配置策略**：引擎类型由 **部署级环境变量** 全局决定；租户级仅扩展 **凭证与桶命名空间**（二期），见 §6.5。

**设计原则**：业务只依赖 `app.infra.storage.ObjectStorage` 门面；实现优先 **MinIO**，协议为 **S3 API**，可切换至阿里云 OSS、AWS S3 等兼容端点（同一 SDK，不同 `endpoint` / `region`）。

```
tenant/kb、workers/ingest、deletion
        │
        ▼
 app.infra.storage.get_object_storage()
        │
        ▼
 S3CompatibleObjectStorage  ← MinIO Python SDK（put/get/delete）
```

| 项 | 说明 |
|----|------|
| 包路径 | `app/infra/storage/`（`base.py` 协议、`s3.py` 实现、`factory.py`） |
| 配置 | `OBJECT_STORAGE_BACKEND=s3`；`OBJECT_STORAGE_ENDPOINT` / `ACCESS_KEY` / `SECRET_KEY` / `BUCKET` / `SECURE` |
| OSS 示例 | `OBJECT_STORAGE_ENDPOINT=oss-cn-hangzhou.aliyuncs.com`，`OBJECT_STORAGE_SECURE=true`，`OBJECT_STORAGE_REGION=cn-hangzhou` |
| PG 字段 | `kb_documents.object_bucket` / `object_key` |
| 入口 | `from app.infra.storage import get_object_storage, upload_bytes, …` |

### 6.3 向量存储

**选型参考**：[vector-database-selection.md](./vector-database-selection.md)（pgvector / Weaviate / Milvus / Qdrant / OpenSearch / ES 对比）。

**配置策略**：向量引擎类型（weaviate / pgvector / milvus）由 **部署级环境变量** 全局决定；**不**按租户混用多种引擎。向量化模型与维度绑在 **知识库**，见 §6.5、§6.6。

**设计原则**：业务只依赖 `app.infra.vector_store.VectorStore`；默认 **Weaviate**，预留 **pgvector**（PostgreSQL 扩展）、**Milvus**。

```
ingest / kb 检索 / deletion
        │
        ├─ 写向量：app.rag.index.upsert_chunk_vector / search_vectors（推荐）
        └─ 读工厂：app.infra.vector_store.get_vector_store()
        │
        ├── weaviate  → WeaviateVectorStore（已实现）
        ├── pgvector  → PgVectorStore（已实现）
        └── milvus    → MilvusVectorStore（已实现，按维度分 Collection）
```

| 项 | 说明 |
|----|------|
| 包路径 | `app/infra/vector_store/`（`ChunkVectorRecord`、`weaviate.py`、`factory.py`） |
| 配置 | `VECTOR_STORE_BACKEND=weaviate` \| `pgvector` \| `milvus` |
| Weaviate | Collection `DocumentChunk`；`Vectorizer.none()` + 客户端 embedding；Filter `tenant_id` + `kb_id` |
| Milvus | Collection `document_chunk_{dimension}`；COSINE；Filter `tenant_id` / `kb_id` / `document_id`；`MILVUS_URI` |
| Embedding | 调用见 §6.6；与向量库类型解耦，与 KB 维度强绑定 |
| PG 引用 | `kb_vector_refs.vector_id` 为向量库中的外部记录 ID |
| 检索门面 | `rag.retrieve.search_kb_chunks`；混合检索 RRF 在 `rag.retrieve.hybrid` |
| LangChain 封装 | `integrations/langchain/vectorstores.py` → `rag.retrieve.multi_kb` |
| 索引门面 | `app.rag.index.gateway`（`upsert_chunk_vector` / `search_vectors` / 删除） |

### 6.5 存储与向量化配置策略

本节约定：**不在租户维度选择「Weaviate 还是 Milvus」** 作为默认产品能力；私有化单实例以 **全局环境变量** 定基础设施，多租户隔离靠 `tenant_id` 与对象 key 前缀；**向量化规格** 在 **知识库** 创建时固化。

#### 6.5.1 为何采用「分层配置」

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 仅全局环境变量 | 运维简单，与 Docker/Helm 一致；单进程一种向量引擎 | 无法「租户自带 OSS」 | **当前默认** |
| 每租户自选引擎类型 | 理论上灵活 | 同实例混跑多种向量库、检索不可跨库、Worker/监控复杂 | **不作为默认** |
| 租户只配凭证 + KB 绑定向量规格 | 兼顾 BYOK 与维度一致 | 需 `resolve_* (tenant_id)` 与 KB 字段 | **推荐演进路径** |

#### 6.5.2 三层配置模型

```mermaid
flowchart TB
    subgraph L1["L1 部署级（环境变量）"]
        OSB["OBJECT_STORAGE_BACKEND=s3"]
        VSB["VECTOR_STORE_BACKEND=weaviate"]
        EMB["EMBEDDING_BACKEND 默认值"]
    end

    subgraph L2["L2 租户级（二期，可选）"]
        OSS["对象存储：endpoint / bucket / AK<br/>sys_configs 或租户扩展表"]
        VSK["向量库：仅连接参数<br/>仍在同一 Weaviate 集群"]
    end

    subgraph L3["L3 知识库级（推荐绑定）"]
        KB["kb_bases.embedding_dimension<br/>+ embedding_profile / model"]
    end

    L1 --> L2
    L1 --> L3
    L2 --> Ingest["ingest / search"]
    L3 --> Ingest
```

| 层级 | 控制什么 | 不控制什么 | 配置载体 | 状态 |
|------|----------|------------|----------|------|
| **L1 部署级** | 对象存储实现（S3 API）、向量引擎种类、默认 embedding 后端 | 单租户 AK、单库维度 | `.env` / `Settings` | ✅ 已实现 |
| **L2 租户级** | 可选：独立 bucket、OSS BYOK（S3 兼容 endpoint/AK/SK） | weaviate vs milvus 二选一 per tenant | `sys_tenant_object_storage` | ✅ BYOK |
| **L3 知识库级** | `embedding_profile`、`embedding_backend`、`embedding_model_name`、`embedding_dimension` | 创建后禁止改维度/模型 | `kb_bases` | ✅ 已实现 |

**隔离约定**：

- 对象：`object_key` 路径含 `tenant_id/kb_id/document_id/...`（已实现）。
- 向量：Weaviate 属性 `tenant_id` + `kb_id` Filter（已实现）；`kb_vector_refs.vector_id` 存外部 ID。
- 同一 KB 内入库与检索必须使用 **相同** `embedding_profile`（含维度与模型）。

#### 6.5.3 运行时解析（目标形态）

```
ingest / search / delete
    │
    ├─ resolve_object_storage(tenant_id?)  → L1 Settings + L2 租户凭证覆盖
    ├─ resolve_vector_store(tenant_id?)    → L1 VECTOR_STORE_BACKEND（L2 仅覆盖 URL/Key）
    └─ load_kb_embedding_profile(kb_id)    → L3 kb_bases 维度与模型
```

工厂 `get_object_storage()` / `get_vector_store()` 保持无 tenant 参数（L1）；租户级覆盖经 `resolve_object_storage_sync/async(tenant_id, db)` 解析（L2 BYOK）。

#### 6.5.4 落地现状

| 层 | 内容 |
|----|------|
| L1 | 环境变量默认端点；`kb_bases.embedding_dimension`；`object_bucket` / `object_key` / `vector_id` 通用字段名 |
| L2 | 租户对象存储 BYOK：`resolve_object_storage_sync/async`；`/system/object-storage` UI |
| L3 | `kb_bases` 绑定 `embedding_profile` / `embedding_model_name`；`GET /kb/embedding-profiles`；创建 KB 选规格（**创建后不可改**）；ingest/检索 `get_embeddings_for_kb` |

向量后端 weaviate / pgvector / milvus **均已实现**，经 L1 切换，不做 per-tenant 混用。

**明确不做（除非单独立项）**：同一部署实例内，租户 A 用 Weaviate、租户 B 用 Milvus 并存。

#### 6.5.5 与「模型供应商」的关系

| 能力 | 配置方式 | 类比 |
|------|----------|------|
| 对话大模型 | `agt_model_configs` + 租户 BYOK | 已上线 |
| 向量化模型 | **KB 级** `embedding_profile` + 全局默认 env | 类似「目录 + 库级绑定」 |
| 对象存储 | L1 端点 + L2 租户 AK（已上线） | 类似 BYOK，但无多引擎 |

对话模型与向量模型 **分开配置**：对话走 LiteLLM `acompletion`；向量走 `get_embeddings_for_kb(kb)`（无 KB 时 `get_embeddings()` 兜底）。

---

### 6.6 向量化（Embedding）

| 项 | 说明 |
|----|------|
| 包路径 | `app/integrations/langchain/embeddings.py`、`app/integrations/litellm/`（对话，非向量） |
| 全局默认 | `EMBEDDING_BACKEND=local` \| `litellm`；`EMBEDDING_MODEL_NAME` / `EMBEDDING_LITELLM_*` |
| 新建 KB | 请求体 `embedding_profile`（默认见 `default_embedding_profile_id()`）；目录 `GET /api/v1/kb/embedding-profiles` |
| 规格目录 | `app/integrations/embedding_profiles.py`：`local-bge-zh`（768）、`dashscope-v3`（1024） |
| 与向量库关系 | 向量库只存 float[]；**维度必须**与 KB 的 `embedding_dimension` 一致，否则禁止入库或检索 |
| 切换模型 | 改全局 env 不影响已有 KB；已有库需 **重建索引**（重新 ingest） |

详见 [ai-stack.md](../guides/ai-stack.md) Embedding 配置表。

---

### 6.7 Redis

- JWT 黑名单、Celery broker/result（常用 db `1`/`2`）、LangGraph checkpoint（`LANGGRAPH_REDIS_DB=0`，需 Redis Stack 或 Redis 8+，否则 MemorySaver）。

---

## 7. API 概览

统一响应：`{ code, message, data, trace_id }`（`common/response.py`）。中间件：`CORS`、`X-Trace-Id`。

### 7.1 租户 `/api/v1`（节选）

| 模块 | 关键端点 |
|------|----------|
| health | `GET /health` |
| auth | `POST /login`, `GET /me`, `POST /refresh` |
| agents | `GET/POST /agents`, `PATCH/DELETE /agents/{id}`, `POST /agents/{id}/chat`, `WS …/chat/ws`, `…/schedules` CRUD |
| attachments | `GET/POST /attachments`, `GET /attachments/{id}/content` |
| media-assets | CRUD + `POST /media-assets/{id}/promote-to-kb` |
| generative | `GET/POST /generative/jobs`, `GET …/stream`（SSE）, `POST …/cancel|retry` |
| tags | `GET/POST /tags`, `GET /tags/meta` |
| categories | `GET /categories` |
| workbench | `GET /workbench/overview` |
| a2a | `GET/POST /a2a/peers`, `POST /a2a/peers/probe`, `POST /a2a/peers/{id}/sync-card` |
| kb | CRUD（创建含 `embedding_profile`）+ `GET /kb/embedding-profiles` + `POST /kb/{id}/documents/upload`, `POST /kb/{id}/search` |
| flows | CRUD + `PUT /flows/{id}/graph`, `POST /flows/{id}/publish`, `/run`, `/compile` |
| compliance | `/compliance/libraries`, `/compliance/bindings`, `POST /compliance/scan`, `GET /compliance/logs`（见 [compliance-word-libraries.md](../guides/compliance-word-libraries.md)） |
| tools | `GET /tools/catalog`, `POST /tools/{name}/invoke` |
| mcp | CRUD + `POST /mcp/{id}/sync`, `POST /mcp/{id}/tools/{name}/invoke` |
| marketplace | `POST /marketplace/apps/from-resources`, `/publish`, `/approve`, `/reject`, `/install`, `/apps/{id}/ratings` |
| monitor | `/monitor/stats`, `/trends`, `/report`, `/health`, `/alerts` |

完整路径以运行实例 **OpenAPI**（`/docs`）为准。

### 7.2 运营 `/api/admin/v1`

`auth/login`、`/tenants`（含 quota）、`/billing/plans`、`/billing/bills`、`/risk/events`、`/risk/ip-blacklist`、`/risk/rate-limits`、`/audit/logs`。

---

## 8. 异步任务

| 组件 | 说明 |
|------|------|
| Broker | `CELERY_BROKER_URL`（通常 Redis） |
| Worker 命令 | `python cli.py worker` 或 `celery -A app.workers.app worker -Q default,parse,ocr,asr,embed` |
| Beat 命令 | `python cli.py beat`（**独立进程**；Docker Compose 默认未含 beat 服务） |
| 入库 | `ingest_document` → `tenant.kb.ingest.run_ingest` → `rag.pipeline.run_ingest_pipeline`（队列 `parse`） |
| 生成 | `run_generative_image_job` / `run_generative_video_job`（队列 `default`；见 [features/task-center.md](../features/task-center.md)） |
| 定时 | Beat 每 60s → `tick_agent_schedules` → `run_agent_schedule` → `AgentService.chat`（见 [features/agent-schedules.md](../features/agent-schedules.md)） |
| 解析链 | `load_documents_from_bytes` → `chunk_documents` → `embed_texts_for_kb` → `upsert_chunk_vector` |
| 可选依赖 | `[parse-docling]`：PDF/Office 版式；`[multimodal]`：图 OCR / 音 Whisper（未装则占位文本仍可入库） |

**任务中心 UI** 聚合两类记录：`GET /tasks`（Celery `task_records`，主要是入库）与 `GET /generative/jobs`（`generative_jobs` 表）。详见 [features/task-center.md](../features/task-center.md)。

任务记录表：`task_records`；API：`GET /tasks`、`POST /tasks/{id}/cancel|retry`。

---

## 9. 流程编排

```
React Flow 画布 → PUT /flows/{id}/graph → flow_versions.graph_json
执行：`get_flow_runtime().run()` → `flow_runtime.runtime_factory` → `integrations.langgraph.flow_runner`
节点：`flow_runtime/nodes/registry.py`
```

**已注册节点类型**：`TextInput`、`TextOutput`、`KnowledgeSearch`、`RelevanceGrade`、`StaticResponse`、`PromptTemplate`、`LLMCall`、`PlatformTool`、`ConditionBranch`、`ParallelJoin`、`ImageGenerate`、`VideoGenerate`、`SubFlow`、`LoopNode` 等（完整列表见 `flow_runtime/nodes/registry.py`）。

- 编译预览：`POST /flows/{id}/compile`（DAG 校验、并行层分析）。
- 智能体绑定 `published_flow_id` 时，对话走同一 LangGraph 执行链。
- 用户指南：[flows.md](../guides/flows.md)。
- **流程编排（属性面板、调试、RAG 节点、SubFlow 已实现）：** [features/flow-orchestration.md](../features/flow-orchestration.md)。

---

## 10. 智能体对话

`POST /api/v1/agents/{id}/chat` 入口：`AgentService.chat`（`tenant/agents/services/agent.py`）。  
**WebSocket（v1）**：`WS /api/v1/agents/{id}/chat/ws`（对话工作台流式/事件总线；设计见 [realtime-transport-design.md](./realtime-transport-design.md)）。

执行前：**钩子** `BEFORE_CALL`、**合规** `check_input`；执行后：`check_output`、`AFTER_CALL`。

```mermaid
flowchart TD
    START[chat] --> TYPE{agent_type?}
    TYPE -->|a2a| HOST[run_a2a_host_chat]
    TYPE -->|custom| SUB{有 sub_agent_bindings?}
    SUB -->|是| DEEP[run_subagent_planned_chat]
    DEEP --> A2A1{有 a2a peer_refs?}
    A2A1 -->|是| AUG[augment_response_with_a2a]
    SUB -->|否| PEER{仅有 peer_refs?}
    PEER -->|是| AUGCHAT[run_a2a_augmented_chat]
    PEER -->|否| FLOW{published_flow_id?}
    FLOW -->|是| FR[flow_runtime + LangGraph]
    FLOW -->|否| RAG{LangGraph RAG?}
    RAG -->|是| LGR[run_rag_workflow]
    RAG -->|否| LIN[legacy rag_answer / ainvoke_chat]
```

| 路径 | 条件 | 实现 |
|------|------|------|
| A2A 宿主 | `agent_type=a2a` | `a2a/invoke.run_a2a_host_chat` |
| 内部协同 | `agt_sub_agent_bindings` 非空 | DeepAgents 或平台 JSON 规划 → `chat_as_child` |
| 引用外部 | `agt_agent_a2a_peer_refs` | 先本地 RAG/流程/协同，再 `augment_response_with_a2a` |
| 画布流程 | `published_flow_id` + 已发布版本 | `get_flow_runtime().run` |
| RAG Graph | 绑 KB、`use_langgraph_rag` 未关闭 | `integrations.langgraph.runner` |
| 线性 RAG | 上述否 | `rag_answer` / 直连 LLM |

- 内部协同：[platform-agents.md](../guides/platform-agents.md)
- A2A：[a2a.md](../guides/a2a.md)
- LangChain/LangGraph/DeepAgents：[ai-stack.md](../guides/ai-stack.md)

### 10.1 多模态（已实现）

识图、生图/生视频、媒体资产、生视频异步任务与任务中心 **已上线**。产品矩阵、代码域与运维见 [multimodal-capabilities.md](../product/multimodal-capabilities.md) §8。

| 文档 | 说明 |
|------|------|
| [multimodal-capabilities.md](../product/multimodal-capabilities.md) | 产品能力矩阵与场景 |
| [features/attachments-media-generative.md](../features/attachments-media-generative.md) | 附件、媒体资产、生成节点实现规格；**附件 v1 不做签名 URL** |

---

## 11. 合规、钩子与工具

### 11.1 合规

- 表：`cmp_sensitive_words`、`cmp_intercept_logs`。
- `ComplianceService`：对话入参/出参扫描；命中写日志。
- 流程 `POST /flows/{id}/run` 同样可走合规（与 agent 配置相关）。

### 11.2 钩子

- 表：`hook_definitions`、`hook_bindings`、`hook_execution_logs`。
- **HTTP 钩子**：Event v1 信封；支持 `block` / `modify`；`config.on_failure`（`ignore` | `fail_request`）。
- **挂载**：Agent chat、Flow run、工具 `invoke_tool_with_context`（`before_tool` / `after_tool`）。
- **Python 钩子**：✅ `hook_type=python`，模块限定 `app.tenant.hooks.plugins.*`。
- **专题**：[hooks.md](../guides/hooks.md)。

### 11.3 工具与 MCP

| 类型 | 状态 |
|------|------|
| 内置工具 | `calculator`、`http_request`、`knowledge_search`、`compliance_check_text`、`run_flow_once`、`invoke_tenant_hook`、`web_search`、`code_execution`、`generate_*`（`tools/invoke.py` + `BUILTIN_REGISTRY`） |
| 自定义 HTTP 工具 | `tool_tools` 表配置 |
| MCP | `tools/list` 同步；HTTP/SSE **`tools/call` 真 invoke**；STDIO 经 `mcp-runner`；`custom` transport，见 [mcp.md](../guides/mcp.md)、[mcp-sandbox.md](./mcp-sandbox.md) |
| 技能包 | `skl_skill_packages` + 磁盘 `SKILL.md`；导入与注入见 [skill-packages.md](../guides/skill-packages.md) |
| 智能体配置 | `config.skill_package_id`、`config.mcp_service_ids` |

---

## 12. 应用市场

- 表：`mkt_categories`、`mkt_apps`、`mkt_ratings`、`mkt_installs`。
- 流程：从 KB/流程/智能体 **打包** → 草稿 → **提交审核**（`pending_review`）→ 运营 **通过/驳回** → 广场列表 → 租户 **安装**（复制 manifest 资源）→ **评分**（需已安装）。
- 权限：`marketplace:review` 审核待审列表。
- 种子：`scripts/seed/marketplace.py` 预置分类。

---

## 13. 前端

### 13.1 租户工作台（`ui/workbench/`，`:3000`）

| 路径 | 功能 |
|------|------|
| `/login` | JWT 登录 |
| `/workbench/dashboard` | 概览 |
| `/workbench/agents` | 智能体列表（Tab：全部 / 智能体 / A2A 互联） |
| `/workbench/agents/chat` | 对话工作台（单智能体调试、会话、定时 Tab） |
| `/workbench/kb`, `/workbench/kb/[id]` | 知识库 |
| `/workbench/media-assets` | 生成素材目录 |
| `/workbench/attachments` | 附件管理 |
| `/workbench/flows`, `/workbench/flows/[id]/edit` | 流程列表与 React Flow 画布 |
| `/workbench/compliance` | 敏感词与日志 |
| `/workbench/prompts` | 提示词模板 |
| `/workbench/models` | 模型供应商 |
| `/workbench/hooks` | 钩子 |
| `/workbench/tools` | 工具 |
| `/workbench/skills`, `/workbench/skills/[id]` | 技能包列表与 SKILL.md 编辑器 |
| `/workbench/mcp` | MCP |
| `/workbench/tasks` | 任务中心 |
| `/workbench/monitor` | 监控统计 |
| `/workbench/marketplace` | 应用市场 |
| `/system/*` | 用户、角色、配置、审计（系统管理区） |

导航：`ui/workbench/lib/nav-config.ts`。API 客户端：`ui/workbench/lib/api.ts`。

### 13.2 运营后台（`ui/admin/`，`:3001`）

登录、租户、计费、风控、审计、个人资料；API 基址 `NEXT_PUBLIC_ADMIN_API_URL` → `/api/admin/v1`。

---

## 14. 部署

### 14.1 Compose 服务（实际）

**基础设施** `docker-compose.infra.yml`（项目根）：`pgvector/pg16`、`redis:8-alpine`、`minio`、`etcd`、`milvus:v2.4.17`、`weaviate:1.24.1`、`flower`（Celery 监控 `:5555`），网络 `milesai-net`。

**应用** `docker-compose.yml`（项目根）：

| 服务 | 说明 |
|------|------|
| `api` | FastAPI，健康检查 `/api/v1/health` |
| `worker` | 单 Celery 进程，多队列（ingest / generative / schedule） |
| `beat` | Celery Beat，智能体定时任务扫描 |
| `mcp-runner` | MCP STDIO 沙箱（`MCP_RUNNER_ENABLED` 时 API 转发 invoke） |

前端 `web` / `admin-web` **不在此 Compose**：由 `npm run build` 产出静态文件部署到 OSS（本地开发各自 `npm run dev`）。

**不是** 多个独立 `worker-parse` / `worker-ocr` 容器；解析/OCR/ASR/向量化由同一 worker 按队列消费。

**向量库默认**：Compose 应用栈默认 `VECTOR_STORE_BACKEND=milvus`；本地/文档示例仍可用 Weaviate（见 `docker-compose.infra.yml`）。

### 14.2 本地仅后端

中间件 Compose + `backend/.env`（`POSTGRES_HOST=localhost`）+ `alembic upgrade head` + `uvicorn app.main:app`。

详见 [operations/deployment.md](../operations/deployment.md)、[database-setup.md](../operations/database-setup.md)、[docker/README.md](../../docker/README.md)。

---

## 15. 配置与环境变量

定义：`backend/app/core/config.py`、`backend/.env.example`、根 `.env.example`。

| 类别 | 变量示例 | 层级（§6.5） |
|------|----------|--------------|
| 应用 | `APP_ENV`, `SECRET_KEY`, `CORS_ORIGINS` | — |
| PostgreSQL | `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, … | — |
| Redis | `REDIS_HOST`, `CELERY_BROKER_URL`, `LANGGRAPH_REDIS_DB`, `LANGGRAPH_REDIS_CHECKPOINT` | L1 |
| 对象存储 | `OBJECT_STORAGE_BACKEND`, `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_ACCESS_KEY`, `OBJECT_STORAGE_SECRET_KEY`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_SECURE`, `OBJECT_STORAGE_REGION` | L1 |
| 向量存储 | `VECTOR_STORE_BACKEND`, `WEAVIATE_*` 或 `MILVUS_URI` / `MILVUS_TOKEN` / `MILVUS_DB_NAME` | L1 |
| 向量化默认 | `EMBEDDING_BACKEND`, `EMBEDDING_MODEL_NAME`, `EMBEDDING_LITELLM_*`, `EMBEDDING_VECTOR_DIMENSION` | L1 默认 / L3 KB |
| RAG 分片 | `DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP` | L3 KB 可覆盖 |
| RAG 解析 | `PARSE_PDF_BACKEND`（`pypdf` \| `docling`）、`PARSE_DOCLING_FALLBACK_PYPDF` | L1；详见 [knowledge-base.md](../guides/knowledge-base.md) §6.4 |
| 种子 | `SEED_ADMIN_USERNAME`, `SEED_PLATFORM_ADMIN_USERNAME` | — |

**大模型 API Key** 存在 `agt_model_configs.api_key_encrypted`，由工作台「模型供应商」配置（租户 BYOK），非环境变量。

**对象/向量引擎类型** 不计划开放为租户自助切换；租户级存储凭证见 §6.5.4。

前端：`NEXT_PUBLIC_API_URL`（租户）、`NEXT_PUBLIC_ADMIN_API_URL`（运营）。

---

## 16. 未完成项（汇总）

已实现能力的完整清单见 [features/](../features/) 与各模块章节；以下为尚未完成的能力：

| 能力 | 状态 | 说明 / 文档 |
|------|------|-------------|
| L2 内置工具扩充（合规检测、触发流程/钩子、列附件） | 🔶 | `compliance_check_text`、`run_flow_once`、`invoke_tenant_hook` ✅；列附件需先补会话/资源范围语义；见 [tools-runtime.md](./tools-runtime.md) §7 |
| 对话 HTTP 整包流式；tool/flow/A2A 路径真 token 流式 | 🔶 | WS 直连/RAG 已真流式；见 [realtime-transport-design.md](./realtime-transport-design.md) |
| WS 断线续传、服务端会话快照 | ⬜ | v2，见 [realtime-transport-design.md](./realtime-transport-design.md) |
| A2A 对外暴露本平台 Agent Card | ⬜ | 现仅能拉取远端 Card；见 [a2a.md](../guides/a2a.md) |
| 技能包 ZIP 导出 / 后端打包 | ⬜ | 见 [skill-packages.md](../guides/skill-packages.md) |
| MCP STDIO 沙箱 MVP 收尾；预置模板/域名白名单 | 🔶 | 见 [mcp-sandbox.md](./mcp-sandbox.md) |
| 视频逐帧 / 流式预览 | ⬜ | 见 [multimodal-capabilities.md](../product/multimodal-capabilities.md) |
| 模型供应商 M4：批量导入、图标资源 | ⬜ | 见 [model-providers.md](../guides/model-providers.md) |
| 离线 OpenAPI 导出 / 离线部署手册 | ⬜ | 文档待补充 |
| 按需延后：短信告警、PDF/Excel 报表、违规统计报表、导出水印、提示词模板 A/B、智能体导出包 | 🔜 | 见 [backlog.md](../product/backlog.md) |
| 按需立项：PaddleOCR / 云 OCR、老格式 Office | 按需 | 见 [backlog.md](../product/backlog.md) |

**后端测试**（`backend/tests/`）：按域分子目录（api / rag / flow / tenant / admin / infra / mcp / a2a 等），详见 [tests/README.md](../../backend/tests/README.md)。

---

## 附录：相关文档

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 文档索引与目录树 |
| [product/prd.md](../product/prd.md) | 立项需求 |
| [frontend/design.md](../frontend/design.md) | 前端设计规范 |
| [operations/database-setup.md](../operations/database-setup.md) | 建库与迁移 |
| [guides/flows.md](../guides/flows.md) | 流程与 RAG Graph |
| [guides/platform-agents.md](../guides/platform-agents.md) | 内部协同 |
| [guides/a2a.md](../guides/a2a.md) | 外部互联 |
| [guides/ai-stack.md](../guides/ai-stack.md) | LangChain 模块与依赖 |
| [guides/model-providers.md](../guides/model-providers.md) | 模型供应商（内置 + 自定义） |
| [features/task-center.md](../features/task-center.md) | 任务中心（入库 + 生成） |
| [features/agent-schedules.md](../features/agent-schedules.md) | 智能体定时任务 |
| [features/attachments-media-generative.md](../features/attachments-media-generative.md) | 附件、媒体资产、生成任务 |
| [features/tags-categories.md](../features/tags-categories.md) | 标签与分类 |
| [features/marketplace.md](../features/marketplace.md) | 应用市场 |
| [features/agent-chat-websocket.md](../features/agent-chat-websocket.md) | 对话 WebSocket |
| [features/system-management.md](../features/system-management.md) | 系统管理 |
| [features/compliance.md](../features/compliance.md) | 安全合规 |
| [features/flow-orchestration.md](../features/flow-orchestration.md) | 流程编排 |
| [features/kb-ingest-retrieval.md](../features/kb-ingest-retrieval.md) | RAG 知识库 |
| [features/tools-mcp-skills.md](../features/tools-mcp-skills.md) | 工具 / MCP / 技能包 |
| [features/models-prompts.md](../features/models-prompts.md) | 模型与提示词 |
| [features/monitor.md](../features/monitor.md) | 监控统计 |
| [features/platform-agents.md](../features/platform-agents.md) | 平台内智能体与内部协同 |
| [features/a2a-interconnect.md](../features/a2a-interconnect.md) | A2A 外部互联 |
| [features/hooks.md](../features/hooks.md) | 智能体钩子 |

---
