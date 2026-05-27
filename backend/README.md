# MilesAi Backend

企业级私有化 AI 编排与 RAG 平台后端（FastAPI）。

## 目录结构

```
cli.py                      # 统一 CLI：serve / worker / migrate / init-db / seed
app/
├── main.py                 # ASGI 入口 (由 cli.py serve 或 uvicorn 加载)
├── apps/
│   ├── application.py      # FastAPI 工厂、生命周期、中间件
│   ├── routers.py          # 路由汇总
│   └── migrate.py          # 启动时 Alembic upgrade
├── tenant/                 # 租户端业务 (/api/v1)
│   ├── router.py
│   ├── auth/               # 登录、Token
│   ├── system/             # 用户、租户、模型、健康检查
│   ├── kb/                 # 知识库与文档摄入
│   ├── flows/              # 编排流程
│   ├── agents/             # 智能体
│   ├── marketplace/        # 应用市场
│   ├── compliance/         # 合规与 Hook
│   ├── tools/              # 工具与 MCP
│   ├── monitor/            # 监控报表
│   ├── tasks/              # Celery 任务管理
│   └── audit_log/          # 租户操作审计
├── admin/                  # 运营后台 (/api/admin/v1)
│   ├── router.py
│   ├── models/             # 运营 ORM（sys / billing / risk / audit）
│   ├── app_sys/            # 平台管理员认证（views / services / repositories）
│   └── app_ops/            # 租户、计费、风控、审计（views / services / repositories）
scripts/                    # db_ops、verify_db、seed/*（由 cli.py 调用）
├── common/                 # 跨模块：响应封装、异常、分页、全局 Handler
├── deletion/               # 删除编排（文档/Agent/KB/Flow/租户级联）
├── utils/                  # 通用工具：idgen、redis_keys、health_checks、orm 索引辅助
├── core/                   # 配置、安全、依赖注入、租户上下文
├── infra/                  # 外部中间件连接
│   ├── db/                 # PostgreSQL（async / sync）
│   ├── redis/
│   ├── storage/            # 对象存储（S3 兼容）
│   └── vector_store/       # 向量库（Weaviate / Milvus / pgvector）
├── models/                 # 核心 ORM（用户、租户、KB、Flow、Agent…）
├── rag/                    # RAG：parse / chunk / index / retrieve / generate / pipeline
├── integrations/           # LangChain / LangGraph / LiteLLM / DeepAgents（L3）
│   ├── langchain/
│   ├── langgraph/
│   └── deepagents/
├── workers/                # Celery 应用与任务
│   ├── app.py
│   └── tasks/
└── middlewares/            # HTTP 中间件（trace、access_log；由 register_http_middlewares 挂载）
```

## 模块约定

| 层级 | 职责 |
|------|------|
| `views/` | FastAPI 路由，薄层，只做参数校验与调用 Service |
| `services/` | 业务逻辑 |
| `schemas/` | Pydantic 请求/响应模型 |
| `repositories/` | 该域数据访问（如 `kb/repositories/kb.py`） |
| `models.py` | 仅该子域拥有的 ORM（如 marketplace、compliance） |
| `constants.py` | 域内多文件共用的字面量（校验、协议字段名）；单文件自用可留在 service |
| `meta.py` | 枚举展示文案（`GET /{module}/meta`）；`schema_version` 用 `META_SCHEMA_VERSION` |

### 单文件体量（强制）

适用于 `app/` 下 **Python 业务与集成代码**（`tenant/`、`rag/`、`integrations/`、`flow_runtime/` 等；测试文件、`alembic/` 版本脚本除外）。

| 阈值 | 要求 |
|------|------|
| **≥ 500 行** | **禁止合并**；必须按下方「子包 per 聚合」拆分后再合入 |
| **400–499 行** | 新增逻辑时优先拆文件或子包，避免继续膨胀 |
| **拆分后** | 单个子模块宜 **300–400 行**；仍超 500 则继续按职责切分 |

自检：在 `backend/` 目录执行 `find app -name '*.py' -exec wc -l {} + | awk '$1 >= 500'`。

### `services/` 子包（按聚合拆分）

当单个 Service 类、或同一聚合下的实现文件 **达到 500 行**、或 mixin/职责块明显增多时，在 `tenant/{domain}/services/{aggregate}/` 下按**业务能力聚合**分子包，而不是在 `services/` 根目录堆 `foo_bar_*.py` 长前缀文件。

函数式模块（如 `tenant/tools/invoke/`）无 `XxxService` 时同样适用：超过 500 行则拆为 `invoke/` 子包 + `builtins/` 等子模块。

**原则**

| 规则 | 说明 |
|------|------|
| 领域边界 | 仍以 `tenant/agents/`、`tenant/compliance/` 等为界；子包只整理该域内的 Service |
| 一个聚合一个目录 | 如 `services/agent/`、`services/compliance/`；目录名与对外 import 模块名一致 |
| 门面 + 导出 | `service.py` 组装 Mixin；`__init__.py` **唯一对外出口**，re-export 公共 API |
| 共享模块上浮 | 被多个聚合引用的代码留在 `services/` 根（如 `agents/services/context.py`、`compliance/services/pipeline.py`） |
| import 稳定 | Views / 集成层继续 `from app.tenant.agents.services.agent import AgentService`，勿改为深层路径 |
| 目录深度 | 一般 **一层子包**即可（`services/agent/chat.py`），避免 `agent/chat/rag/` 等多级套娃 |

**已落地的聚合包**

```
tenant/agents/services/
  agent/              # AgentService：crud.py、chat.py、serialization.py、service.py
  architecture.py     # 独立 Service，与 agent 并列
  schedule.py / stats.py / context.py / sub_agents.py

tenant/compliance/services/
  compliance/         # ComplianceService：intercept、scan_bindings、library、…
  pipeline.py / word_resolve.py

tenant/marketplace/services/
  marketplace/        # MarketplaceService：catalog、publish、install、review、ratings

tenant/tools/
  invoke/             # 工具执行（函数式门面，无 XxxService 类）
  builtins/           # 各内置 slug 的 handler，由 invoke/builtin.py 分发
```

**新增子包步骤**：新建 `services/{aggregate}/` → 按职责拆 `*.py` → 在 `service.py` 用 Mixin 组合 → `__init__.py` 导出 → 删除同名旧 `services/{aggregate}.py`（不能与目录共存）→ 跑该域 pytest。

### 文档注释（类 / 方法 / 函数）

`app/` 下业务代码须为 **模块、类、公开方法、模块级函数** 编写 **中文 docstring**（`"""..."""`），不写无意义的 `#` 行注释堆砌。

| 对象 | 要求 |
|------|------|
| 模块 | 文件顶部说明职责；子包 `__init__.py` 说明对外 export |
| 类 / Mixin | 一句话说明聚合职责 |
| 方法 / 函数 | 说明做什么、关键副作用（抛错、写库、调外部） |
| 私有 `_xxx` | 有独立业务逻辑则完整说明；避免无意义的公开方法转发 |

新增或拆出的子包代码 **合入前** 应补全 docstring；与 [layering.md](../docs/architecture/layering.md) §5.5 一致。

**常量分家**（勿建全局 `app/constants/`）：`models.Enum` 为持久化真源；`tenant/*/meta.py` 仅 label/hint；`integrations/*/constants.py` 为协议与 `ModelConfig.extra` 键；跨模型 extra 键见 `common/constants/model_extra.py`；Redis 键见 `utils/redis_keys.py`。

- Hook Event `schema_version`（`hooks/events.SCHEMA_VERSION`）与 `GET */meta` 的 `META_SCHEMA_VERSION` 为两套契约，见 [docs/guides/hooks.md](../docs/guides/hooks.md) §9.1。
- embedding/rerank 的 `extra` 键对照见 [docs/guides/model-config-extra.md](../docs/guides/model-config-extra.md)。

共享 ORM 放在 `app/models/`；租户子域表在 `tenant/*/models.py`；运营表在 `admin/models/`（按域拆分文件）。**表名与索引在各模型文件的 `__tablename__` / `__table_args__` 中定义**（无 `common/tables.py`）。

**表名域前缀**：

| 前缀 | 域 | 示例 |
|------|-----|------|
| `sys_` | 租户 / 用户 / RBAC | `sys_tenants`、`sys_users` |
| `kb_` | 知识库 | `kb_bases`、`kb_documents` |
| `agt_` | 智能体 | `agt_agents`、`agt_kb_bindings` |
| `flow_` | 编排 | `flow_flows`、`flow_versions` |
| `task_` | 任务 | `task_records` |
| `cmp_` | 合规 | `cmp_sensitive_words` |
| `tool_` | 工具 | `tool_tools`、`tool_mcp_services` |
| `mkt_` | 应用市场 | `mkt_apps`、`mkt_installs` |
| `aud_` | 租户审计 | `aud_logs` |
| `adm_` | 运营后台 | `adm_admins`、`adm_audit_logs` |

数据库迁移仅保留 `alembic/versions/001_initial_schema.py`（按 ORM metadata 一次性建表）。

- **新环境 / 清库后**：`alembic upgrade head` 或 `python cli.py init-db`
- **已有库且 schema 已与当前 ORM 一致**（曾跑过旧 002–015 链）：`alembic stamp 001`，勿重复 upgrade

**逻辑外键**：ORM 列使用 UUID，不建数据库 `FOREIGN KEY`；关联用 `relationship(..., foreign_keys=..., primaryjoin=...)`。删除级联由应用层或 `relationship(cascade=...)` 负责。

**索引命名**（在模型 `__table_args__` 显式声明）：

| 前缀 | 含义 |
|------|------|
| `idx_` | 普通单列索引 |
| `uk_` | 唯一索引/约束 |
| `un_` | 联合非唯一索引 |

辅助模块：`app/utils/orm.py`（`idx` / `uk` / `un` 工厂函数，可选使用）。

**主键 ID**：数据库主键与 Weaviate 对象 ID 均使用 **UUIDv7**（`app/utils/idgen.py`），时间有序，利于 B-tree / 向量库索引；JWT `jti`、HTTP `X-Trace-Id` 仍可用随机 UUID。

**Alembic 模型登记**：勿在 `models/__init__.py` 反向导入 `admin`（会循环引用）。新增 ORM 模块后，在 `app/models/registry.py` 的 `load_all_models()` 中补一行 import。

**包 `__init__.py`**：各层目录均已补齐；`flow_runtime/templates/` 仅存放 JSON 模板，无需 `__init__.py`。顶层 `admin/`、`tenant/` 的 `__init__.py` 仅作文档，不在此 eager import 路由，避免循环依赖。

### RAG（`app/rag/`）

| 模块 | 说明 |
|------|------|
| `parse/loaders.py` | 入库解析入口：TXT/MD、PDF（pypdf/docling）、图片、音频 |
| `chunk/splitter.py` | `chunk_documents` → `TextChunk`（含 `page_no`） |
| `pipeline/ingest.py` | `run_ingest_pipeline`（Parse → Chunk → Embed → Index） |
| `index/gateway.py` | 向量 upsert/search 门面 |
| `retrieve/` | `search_kb_chunks`、hybrid、多 KB |
| `generate/` | RAG 上下文与回答 |

可选依赖：`pip install -e ".[parse-docling]"`、`pip install -e ".[multimodal]"`。详见 [docs/guides/knowledge-base.md](../docs/guides/knowledge-base.md)、[docs/architecture/layering.md](../docs/architecture/layering.md)。

### 流程运行时（`flow_runtime/`）

| 模块 | 说明 |
|------|------|
| `runtime_factory.get_flow_runtime()` | 入口 → LangGraph 编译执行画布 |
| `nodes/registry.py` | 节点注册（RAG / LLM / IO 等） |

业务 CRUD 与 `POST /flows/{id}/run` 在 `tenant/flows/`。完整说明见 [docs/guides/flows.md](../docs/guides/flows.md)。

### Admin 布局

**ORM**（`admin/models/`，与 `app_sys` / `app_ops` 平级）：

| 文件 | 表 |
|------|-----|
| `sys.py` | `adm_admins` |
| `billing.py` | `adm_billing_plans`、`adm_tenant_bills`、`adm_bill_line_items` |
| `risk.py` | `adm_risk_events`、`adm_ip_blacklist`、`adm_rate_limit_rules` |
| `audit.py` | `adm_audit_logs` |

**DTO**（仍在各 app 子包内）：

- `app_sys/schemas/auth.py` — 登录、Token、改密、会话
- `app_ops/schemas/{tenant,billing,risk,audit}.py` — 对应 API 请求/响应
- `app_sys/views/`、`app_ops/views/` — 路由薄层（`router.py` 仅汇总 include）

### 删除编排（`app/deletion/`）

无数据库外键时，删除顺序由编排模块保证：

| 方法 | 清理范围 |
|------|----------|
| `clear_document_derived_data_*` | vector_refs、document_chunks、Weaviate |
| `before_delete_agent` | agent_kb_bindings、应用安装引用、Agent 域 Hook |
| `before_delete_kb` | 绑定表、应用安装 kb_id |
| `before_delete_flow` | flow_versions、Agent.published_flow_id、应用安装 flow_id、Flow Hook |
| `purge_tenant_data` | 租户下全部业务表（供运营删租户前调用，不删 tenants 行） |

流程删除 API：`DELETE /api/v1/flows/{flow_id}`。

### 可选后续优化

| 项 | 说明 |
|----|------|
| 中间件落地 | trace / access_log 已在 `middlewares/`；IP 黑名单、限流等待补充 |
| 运营删租户 | 在 `AdminTenantService` 中调用 `purge_tenant_data` 后再删租户记录 |

## 统一 CLI（`cli.py`）

运维与启动统一入口；种子实现仍在 `scripts/seed/`（与 `app` 解耦）。API lifespan **只跑迁移**，不自动写种子。

```bash
cd backend
python cli.py serve              # uvicorn（debug 默认 --reload）
python cli.py serve --no-reload
python cli.py worker             # Celery worker
python cli.py migrate            # alembic upgrade head
python cli.py init-db            # 迁移 + 全量种子
python cli.py init-db --seed-only
python cli.py seed tenant        # 单域种子：tenant | tools | mcp | flows | skills | hooks | … | all
python cli.py verify-db          # 检查核心表
python cli.py backfill-media-assets [--dry-run] [--tenant-id UUID]  # 历史生成物登记
```

`pip install -e .` 后可使用全局命令 `milesai serve`。

## 常用命令

```bash
python cli.py serve
python cli.py init-db
python cli.py worker -Q parse,default
```

## API 前缀

- 租户端：`/api/v1`
- 运营端：`/api/admin/v1`（JWT `type: admin_access`，与租户 Token 不可混用）
