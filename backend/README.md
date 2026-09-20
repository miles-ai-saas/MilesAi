# MilesAi Backend

企业级私有化 AI 编排与 RAG 平台后端（FastAPI）。

## 目录结构

```
backend/
├── pyproject.toml           # uv workspace 根（成员 packages/*，收敛 ruff/pytest 配置）
├── uv.lock                  # 工作区唯一锁文件
├── .importlinter            # 6 条包分层契约（make layers-check）
├── alembic/                 # 迁移（env.py 引用 miles_core）
├── openapi/openapi.snapshot.json
├── tests/                   # 单一测试套件
├── tools/                   # 一次性 codemod（rename_to_workspace.py）
└── packages/                # 10 个 uv workspace 包，源码在 <pkg>/src/<module>/
    ├── miles-common/   → src/miles_common/    # 跨模块公共能力：响应/异常/schema、idgen、redis_keys
    ├── miles-exec/     → src/miles_exec/      # 沙箱 + MCP 协议内核
    ├── miles-core/     → src/miles_core/      # L4：infra/、models/、web/、risk/、jobs/、utils/
    ├── miles-ai/       → src/miles_ai/        # L2/L3：rag/、integrations/、flow_runtime/
    ├── miles-portal/   → src/miles_portal/    # L0/L1：tenant/、deletion/、marketplace/ + register_portal
    ├── miles-admin/    → src/miles_admin/     # L0/L1：admin/ + register_admin
    ├── miles-openapi/  → src/miles_openapi/   # /api/v1/open/* + register_open
    ├── miles-server/   → src/miles_server/    # 装配根：apps/、main.py、cli.py、scripts/
    ├── miles-worker/   → src/miles_worker/    # Celery app + tasks/
    └── miles-runner/   → src/miles_runner/    # 沙箱 HTTP 服务（自带 settings）
```

> `cli.py`、`scripts/`（db_ops、verify_db、seed/*、export_openapi）已迁入 `miles-server`；旧单包目录 `backend/app` 与 `backend/cli.py` 已不存在。包边界与 API 层归属见 [layering.md §2.4 / §2.5](../docs/architecture/layering.md)。
>
> `packages/` 与 `src/` 两层只为物理组织，**不进 `sys.path`**，故导入路径始终是 `miles_core.…` 这类形式，与层数无关（`src/` 用 PyPA 推荐的 src layout 防 cwd 影子导入）。**不要为缩短路径而合并层级**——`parents[N]` 已按此深度硬编码在 `miles_server/apps/migrate.py` 等处。查模块实际位置：`python -c "import miles_core; print(miles_core.__file__)"`。

## 安装与运行

```bash
cd backend
uv sync --all-packages --group dev          # 安装 10 个包 + dev 依赖（pytest / ruff / import-linter）
uv run milesai migrate                      # alembic upgrade head
uv run milesai init-db                      # 迁移 + 全量种子
uv run milesai serve                        # 启动 API（debug 默认热重载）
uv run milesai worker                       # Celery Worker
uv run milesai beat                         # Celery Beat（可选，独立进程）
uv run milesai verify-db                    # 检查核心表
```

`milesai` 由 `packages/miles-server/pyproject.toml` 的 `[project.scripts]` 声明（`miles_server.cli:main`）；也可用 `python -m miles_server.cli <cmd>`。解析 / 多模态 / OTel 等可选能力已按所属包无条件声明（`miles-ai` / `miles-server`），随 `uv sync` 一并安装。

**质量门禁**：`make check`（= ruff check + ruff format --check + layers-check + openapi-check + pytest），单独跑分层契约用 `make layers-check`。

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

适用于 `backend/packages/*/src/` 下 **Python 业务与集成代码**（如 `miles_portal` 的 `tenant/*`、`miles_ai` 的 `rag/` 与 `integrations/`、`miles_ai/flow_runtime/` 等；测试文件、`alembic/` 版本脚本除外）。

| 阈值 | 要求 |
|------|------|
| **≥ 500 行** | **禁止合并**；必须按下方「子包 per 聚合」拆分后再合入 |
| **400–499 行** | 新增逻辑时优先拆文件或子包，避免继续膨胀 |
| **拆分后** | 单个子模块宜 **300–400 行**；仍超 500 则继续按职责切分 |

自检：在 `backend/` 目录执行 `find packages -path '*/src/*' -name '*.py' -exec wc -l {} + | awk '$1 >= 500'`。

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
| import 稳定 | Views / 集成层继续 `from miles_portal.tenant.agents.services.agent import AgentService`，勿改为深层路径 |
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

`backend/packages/*/src/` 下业务代码须为 **模块、公开方法、模块级函数** 编写 **中文 docstring**（`"""..."""`），不写无意义的 `#` 行注释堆砌。

| 对象 | 要求 |
|------|------|
| 模块 | 文件顶部说明职责；子包 `__init__.py` 说明对外 export |
| 类 / Mixin（有行为：service / 聚合 / 工具 / 节点） | docstring 一句话说明聚合职责 |
| 数据载体类（Pydantic DTO / `str, Enum`） | 允许用类上方**一行** `#` 注释说明用途（现网统一约定）；说明多于一行或含行为时改用 docstring |
| 方法 / 函数 | 说明做什么、关键副作用（抛错、写库、调外部） |
| 私有 `_xxx` | 有独立业务逻辑则完整说明；避免无意义的公开方法转发 |

> DTO 的 `#` 注释**不会**进入 OpenAPI：Pydantic v2 仅取类 docstring 作为该模型的 `description`。若把 DTO 注释改为 docstring，会新增 schema 描述，须执行 `make openapi-write` 更新快照。

新增或拆出的子包代码 **合入前** 应补全 docstring；与 [layering.md](../docs/architecture/layering.md) §5.5 一致。

**常量分家**（勿建全局 `constants/` 包）：`models.Enum` 为持久化真源；`tenant/*/meta.py` 仅 label/hint；`integrations/*/constants.py` 为协议与 `ModelConfig.extra` 键；跨模型 extra 键见 `miles_common/constants/model_extra.py`；Redis 键见 `miles_common/redis_keys.py`。

- Hook Event `schema_version`（`hooks/events.SCHEMA_VERSION`）与 `GET */meta` 的 `META_SCHEMA_VERSION` 为两套契约，见 [docs/guides/hooks.md](../docs/guides/hooks.md) §9.1。
- embedding/rerank 的 `extra` 键对照见 [docs/guides/model-config-extra.md](../docs/guides/model-config-extra.md)。

共享 ORM 放在 `miles_core/models/`；租户子域表在 `miles_portal/tenant/*/models.py`；运营表在 `miles_admin/models/`（按域拆分文件）。**表名与索引在各模型文件的 `__tablename__` / `__table_args__` 中定义**（无集中式 `tables.py`）。

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

- **新环境 / 清库后**：`milesai init-db`（或 `alembic upgrade head`）
- **已有库且 schema 已与当前 ORM 一致**（曾跑过旧 002–015 链）：`alembic stamp 001`，勿重复 upgrade

**逻辑外键**：ORM 列使用 UUID，不建数据库 `FOREIGN KEY`；关联用 `relationship(..., foreign_keys=..., primaryjoin=...)`。删除级联由应用层或 `relationship(cascade=...)` 负责。

**索引命名**（在模型 `__table_args__` 显式声明）：

| 前缀 | 含义 |
|------|------|
| `idx_` | 普通单列索引 |
| `uk_` | 唯一索引/约束 |
| `un_` | 联合非唯一索引 |

辅助模块：`miles_core/utils/orm.py`（`idx` / `uk` / `un` 工厂函数，可选使用）。

**主键 ID**：数据库主键与 Weaviate 对象 ID 均使用 **UUIDv7**（`miles_common/idgen.py`），时间有序，利于 B-tree / 向量库索引；JWT `jti`、HTTP `X-Trace-Id` 仍可用随机 UUID。

**Alembic 模型登记**：勿在 `miles_core/models/__init__.py` 反向导入 `admin`（会循环引用）。新增 ORM 模块后，把模块名加进 `miles_server/registry.py` 的 `_ORM_MODULES`（顺序无关）。漏加会被 `tests/models/test_orm_registry_completeness.py` 挡下——否则 `Base.metadata` 缺表，Alembic autogenerate 会把已有表判成待 DROP 的差异。

**包 `__init__.py`**：各层目录均已补齐；`flow_runtime/templates/` 仅存放 JSON 模板，无需 `__init__.py`。顶层 `admin/`、`tenant/` 的 `__init__.py` 仅作文档，不在此 eager import 路由，避免循环依赖。

### RAG（`miles_ai.rag`）

| 模块 | 说明 |
|------|------|
| `parse/loaders.py` | 入库解析入口：TXT/MD、PDF（pypdf/docling）、图片、音频 |
| `chunk/splitter.py` | `chunk_documents` → `TextChunk`（含 `page_no`） |
| `pipeline/ingest.py` | `run_ingest_pipeline`（Parse → Chunk → Embed → Index） |
| `index/gateway.py` | 向量 upsert/search 门面 |
| `retrieve/` | `search_kb_chunks`、hybrid、多 KB |
| `generate/` | RAG 上下文与回答 |

解析 / 多模态依赖（`pypdf`、`docling`、`pytesseract`、`openai-whisper`）已在 `miles-ai` 中无条件声明，随 `uv sync` 安装。详见 [docs/guides/knowledge-base.md](../docs/guides/knowledge-base.md)、[docs/architecture/layering.md](../docs/architecture/layering.md)。

### 流程运行时（`miles_ai.flow_runtime`）

| 模块 | 说明 |
|------|------|
| `runtime_factory.get_flow_runtime()` | 入口 → LangGraph 编译执行画布 |
| `nodes/registry.py` | 节点注册（RAG / LLM / IO 等） |

业务 CRUD 与 `POST /flows/{id}/run` 在 `tenant/flows/`。完整说明见 [docs/guides/flows.md](../docs/guides/flows.md)。

### Admin 布局

**ORM**（`miles_admin/models/`，与 `app_sys` / `app_ops` 平级）：

| 文件 | 表 |
|------|-----|
| `sys.py` | `adm_admins` |
| `billing.py` | `adm_billing_plans`、`adm_tenant_bills`、`adm_bill_line_items` |
| `risk.py` | `adm_risk_events`、`adm_ip_blacklist`、`adm_rate_limit_rules` |
| `audit.py` | `adm_audit_logs` |

**DTO**（在各 admin 子包内）：

- `app_sys/schemas/auth.py` — 登录、Token、改密、会话
- `app_ops/schemas/{tenant,billing,risk,audit}.py` — 对应 API 请求/响应
- `app_sys/views/`、`app_ops/views/` — 路由薄层（`router.py` 仅汇总 include）

> **运营面读租户域数据**（审核/监管）：仅限 `admin → tenant` 单向，且优先经共享 ORM（`miles_core/models/`）与下沉的纯函数/Repository；合规形态与过渡期例外见 [layering.md §2.3](../docs/architecture/layering.md#23-运营后台admin访问租户域)。

### 删除编排（`miles_portal.deletion`）

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
| 中间件落地 | trace / access_log / platform_risk（IP 黑名单 + 按 `scope` 维度的限流）已在 `middlewares/` |
| 运营删租户 | 在 `AdminTenantService` 中调用 `purge_tenant_data` 后再删租户记录 |

## 统一 CLI（`milesai` / `miles_server.cli`）

运维与启动统一入口；种子实现仍在 `miles_server/scripts/seed/`（与各域包解耦）。API lifespan **只跑迁移**，不自动写种子。

> 项目根 `Makefile` 已封装以下命令（`make help` 查看全部）：`make init-db`、`make serve`、`make worker`、`make beat`、`make check`、`make layers-check`、`make openapi-check` 等，会自动探测 `backend/.venv` 下的解释器与 ruff。

```bash
cd backend
uv run milesai serve              # uvicorn（debug 默认 --reload）
uv run milesai serve --no-reload
uv run milesai worker             # Celery worker
uv run milesai migrate            # alembic upgrade head
uv run milesai init-db            # 迁移 + 全量种子
uv run milesai init-db --seed-only
uv run milesai seed tenant        # 单域种子：tenant | tools | mcp | flows | skills | hooks | … | all
uv run milesai verify-db          # 检查核心表
uv run milesai backfill-media-assets [--dry-run] [--tenant-id UUID]  # 历史生成物登记
```

`uv sync --all-packages --group dev` 后即可使用 `milesai`；也可用 `python -m miles_server.cli <cmd>`。

## 常用命令

```bash
uv run milesai serve
uv run milesai init-db
uv run milesai worker -Q parse,default
```

## OpenAPI 快照

仓库内维护 FastAPI 契约快照，防止 API schema 无意漂移；CI（`.github/workflows/lint.yml`）会执行校验。

| 命令 | 说明 |
|------|------|
| `python -m miles_server.scripts.export_openapi --check` | 与 `openapi/openapi.snapshot.json` 比对（**默认**；CI 同款） |
| `python -m miles_server.scripts.export_openapi --write` | 重写快照（改路由/Schema 后本地执行并提交） |

脚本调用 `create_app().openapi()`，**无需启动 uvicorn**，也不依赖 Postgres/Redis 等中间件。

等价 Makefile 目标：`make openapi-check`（校验）、`make openapi-write`（重写）。

```bash
cd backend
python -m miles_server.scripts.export_openapi --check   # 校验
python -m miles_server.scripts.export_openapi --write   # 更新 openapi/openapi.snapshot.json
```

## OpenTelemetry（OTel）

API 进程可选向 OTLP Collector 导出 HTTP 请求 trace；**默认关闭**，Celery Worker/Beat **未**接入。

### 安装

OTel 依赖（`opentelemetry-api` / `sdk` / `exporter-otlp` / `instrumentation-fastapi`）已在 `miles-server` 中无条件声明，随 `uv sync --all-packages` 安装；`OTEL_ENABLED=false`（默认）时仅 no-op。

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `OTEL_ENABLED` | `false` | 总开关 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 空 | 启用时必填；空则 no-op |
| `OTEL_SERVICE_NAME` | `milesai-api` | resource `service.name` |

### 导出协议

当前实现使用 **gRPC OTLP**（`opentelemetry.exporter.otlp.proto.grpc`），Collector 常见端口为 **4317**。设计稿曾提及 HTTP/protobuf（4318）为可选方案，**尚未实现**；若 Collector 仅监听 HTTP 4318，需后续增加协议配置或换 HTTP exporter。

请求头 `X-Trace-Id` 会写入 span attribute `miles.trace_id`，与现有 `TraceMiddleware` 并存，不替换 W3C `traceparent`。

## API 前缀

- 租户端：`/api/v1`
- 运营端：`/api/admin/v1`（JWT `type: admin_access`，与租户 Token 不可混用）
