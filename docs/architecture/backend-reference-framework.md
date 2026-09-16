# 后端参考框架（Backend Reference Framework）

> 面向读者：**其他 LLM / 开发者**。用途：快速搭建一个**企业级、多租户、RAG + 编排类 AI 应用后端**的可复用骨架。
>
> 本文从 MilesAi 的真实后端提炼而来，剥离具体业务（知识库、智能体、流程、市场等），只保留**可移植的架构模式、横切设施骨架、目录约定与护栏**。
> 阅读时把 `{project}`、`{domain}`、`{table_prefix}` 等占位符替换为新项目的命名即可。

---

## 0. 这份文档怎么用

1. 先读 §1「技术栈」确定选型，§2「分层」理解依赖方向。
2. 按 §3「目录模板」搭出空骨架（或直接按模板创建目录与 `__init__.py`）。
3. 按 §4「横切设施」落地 `core/`、`common/`、`infra/` 的通用代码（这些是所有域共享的地基）。
4. 每新增一个业务域，套用 §5「业务域模板」的四件套 + §6 的 ORM 约定。
5. 对外部系统（对象存储、向量库等）一律走 §7 的「协议 + 工厂」抽象。
6. 长任务走 §8 的 Celery；收尾按 §9「护栏」自检，按 §10「Checklist」验收。
7. 进阶主题（认证会话/RBAC、审计、级联删除、任务状态机、Hook 切面、安全风控、测试、反模式）见 §11–§17。

核心心智模型只有一句话：**请求从「薄路由」进入，经过「用例服务」，下沉到「领域能力」与「基础设施」，且依赖方向严格单向。**

---

## 1. 技术栈与选型

| 关注点 | 选择 | 理由 / 可替换项 |
|--------|------|----------------|
| Web 框架 | FastAPI（`>=0.115`） | 原生 async、自动 OpenAPI、依赖注入 |
| 应用工厂 | 模块级 `create_app()` | 便于测试与 CLI 复用，见 §4.1 |
| ORM | SQLAlchemy 2.0（async）+ asyncpg | 显式 `Mapped`/`mapped_column` 类型注解 |
| 迁移 | Alembic | 启动时 `upgrade head`，见 §6.4 |
| 数据校验 | Pydantic v2 + pydantic-settings | 配置用 `BaseSettings`，DTO 用 `BaseModel` |
| 认证 | JWT（python-jose）+ bcrypt | access/refresh 双 token，见 §4.4 |
| 任务队列 | Celery + Redis | 多队列路由 + Beat 定时，见 §8 |
| 数据库 | PostgreSQL | UUID、JSONB、BigInteger 配额字段 |
| 缓存/黑名单 | Redis | JWT 黑名单、Celery broker、LangGraph checkpoint |
| 对象存储 | S3 兼容协议（MinIO 默认） | 门面 + 可切 OSS/AWS S3，见 §7.2 |
| 向量库 | Weaviate / Milvus / pgvector | 门面 + 工厂，见 §7.3 |
| 日志 | stdlib `logging.config` | 幂等 `setup_logging()`，见 §4.9 |
| 可观测 | OpenTelemetry | 依赖随 miles-server 安装；默认关闭，`OTEL_ENABLED` 开关 |

> 若新项目**不需要**向量/RAG，可整段删除 `rag/` 层与向量库抽象，其余骨架不变——分层模型天然支持这种裁剪。

---

## 2. 总体架构

### 2.1 进程拓扑

```text
                    ┌─────────────┐
  HTTP 客户端 ─────►│  API 进程    │  FastAPI（/api/v1 租户 · /api/admin/v1 运营）
                    └──────┬──────┘
                           │ 入队（Celery）
                    ┌──────▼──────┐      ┌─────────────┐
                    │  Worker 进程 │      │  Beat 进程    │  定时扫描/调度
                    └──────┬──────┘      └─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  PostgreSQL（业务元数据）  Redis（缓存/队列）  对象存储 + 向量库（大对象/向量）
```

要点：
- **API 与 Worker 共享同一套 workspace 包代码**，只是入口不同（`milesai serve` vs `milesai worker`）。
- **迁移只由 API 启动时执行**；种子数据单独由 CLI 显式写入（见 §6.4）。
- 可选独立进程（如 MCP 沙箱、多模态 OCR）通过额外容器部署，**不**塞进 API 进程。

### 2.2 分层与依赖方向（强制单向）

```text
L0 路由        tenant/{domain}/views/ · admin/*/views/      HTTP / 鉴权 / DTO 校验
      │
L1 用例        tenant/{domain}/services/ · admin/*/services  业务状态机 / 配额 / 编排
      │
L2 领域能力    rag/  flow_runtime/                            领域算法（可裁剪）
      │
L3 集成        integrations/  （langchain / langgraph / litellm） 第三方 SDK 封装
      │
L4 基础设施    infra/  （db / redis / storage / vector_store）     连接池 / 客户端原语
```

**依赖规则**：只允许 `L0 → L1 → L2 → L3 → L4`。禁止反向；禁止跨层跳用（L1 不直接 import L4 的具体客户端，应经 L2 门面或 L4 工厂）。

落地约束（可写进 `.cursorrules` / `AGENTS.md`）：

- `infra/` 不得 import `tenant/`、`rag/`（基础设施不懂业务）。
- `integrations/` 不得 import `tenant/`（参数由 L2 传入）。
- `rag/` 可 import `models`、`infra`，但**不** import `tenant/*/services`。
- 同级域（如 `tenant/agents` 与 `tenant/flows`）不直接 import 对方内部文件，共享代码下沉 `lib/` 或 `models/`。

---

## 3. 目录结构模板

```text
{project}/backend/
├── pyproject.toml               # uv workspace 根 + [dependency-groups].dev
├── uv.lock
├── alembic.ini
├── alembic/
│   └── versions/                # 001_initial_schema.py 等
├── openapi/                     # openapi.snapshot.json（契约快照，防漂移）
├── tests/                       # api/ integration/ rag/ tenant/ …
└── packages/                    # 10 个 uv workspace 包，源码在 <pkg>/src/<module>/
    ├── miles-common/src/miles_common/   # 跨域横切：响应/异常/schema、idgen、redis_keys、constants/
    ├── miles-exec/src/miles_exec/       # 沙箱 + MCP 协议内核
    ├── miles-core/src/miles_core/       # L4 基础设施 + 核心 ORM + 配置/安全/依赖注入
    │   ├── config.py  security.py  deps.py  tenant.py  logging.py
    │   ├── repository.py  service.py  soft_delete.py  field_crypto.py
    │   ├── infra/                       # db/ redis/ storage/ vector_store/ otel.py
    │   ├── models/                      # 核心 ORM（按域分子包）+ base.py
    │   ├── web/                         # 通用 Web 管道：handlers.py + middlewares/
    │   └── risk/  jobs/  utils/         # orm / health_checks
    ├── miles-ai/src/miles_ai/           # L2/L3：rag/、integrations/、flow_runtime/
    ├── miles-portal/src/miles_portal/   # L0/L1 租户业务域（/api/v1）
    │   ├── registration.py              # register_portal(app)
    │   ├── tenant/                      # 每域 views/services/repositories/schemas
    │   │   └── {domain}/                # models.py / meta.py / constants.py
    │   ├── deletion/                    # 无外键时的级联删除编排
    │   └── marketplace/
    ├── miles-admin/src/miles_admin/     # L0/L1 运营后台（/api/admin/v1）
    │   ├── registration.py              # register_admin(app)
    │   ├── models/                      # 运营 ORM
    │   └── app_sys/  app_ops/           # 管理员认证 / 运营业务
    ├── miles-openapi/src/miles_openapi/ # /api/v1/open/* + registration.py
    ├── miles-server/src/miles_server/   # 装配根：apps/application.py、main.py、cli.py、scripts/
    ├── miles-worker/src/miles_worker/   # Celery：app.py + tasks/
    └── miles-runner/src/miles_runner/   # 沙箱 HTTP 服务（自带 settings）
```

**域内四件套约定**（每个 `{domain}/` 都遵守）：

| 目录 | 职责 | 是否薄 |
|------|------|--------|
| `views/` | FastAPI 路由，只做参数校验 + 依赖注入 + 调 Service | 薄 |
| `services/` | 业务逻辑、租户校验、编排、调 `rag.*` / `integrations.*` | 厚 |
| `repositories/` | 该域数据访问（可选；简单域可把查询写进 Service） | 中 |
| `schemas/` | Pydantic 请求/响应模型 | — |

---

## 4. 横切设施（可复制骨架）

以下是所有业务域共享的地基，与具体业务无关，可直接迁移。

### 4.1 应用装配（`apps/application.py` + `main.py`）

```python
# miles_server/main.py
from miles_server.apps.application import create_app
app = create_app()
```

```python
# miles_server/apps/application.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from miles_admin.registration import register_admin
from miles_core.web.handlers import exception_handlers
from miles_core.web.middlewares import register_http_middlewares
from miles_openapi.registration import register_open
from miles_portal.registration import register_portal
from miles_server.apps.migrate import run_migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动期只做迁移 + 需要初始化的资源；种子数据不在此处写入
    run_migrations()
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        openapi_url="/openapi.json", docs_url="/docs",
        exception_handlers=exception_handlers,
        debug=False,               # 关键：True 会绕过统一信封
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origin_regex=r".*",
                       allow_credentials=True, allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["X-Trace-Id"])
    register_http_middlewares(app)
    register_open(app)      # /api/v1/open/*
    register_portal(app)    # /api/v1
    register_admin(app)     # /api/admin/v1
    return app
```

**要点**：`debug=False` 固定写死，避免 Starlette 明文 traceback 绕过统一错误信封。

### 4.2 配置（`core/config.py`）

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MyApp"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "myapp"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def database_url(self) -> str:
        return (f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**要点**：`extra="ignore"` 容忍未知变量；`@lru_cache` 保证单例；敏感配置（如 LLM API Key）**不放**环境变量，而存业务表并用 §4.8 加密。

### 4.3 统一响应与异常

```python
# miles_common/schema.py
from typing import Generic, TypeVar
from pydantic import BaseModel, Field
T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="0 表示成功")
    message: str = Field(default="ok")
    data: T | None = None
    trace_id: str | None = None

class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100)
    @property
    def offset(self) -> int: return (self.page - 1) * self.size

class PageResult(BaseModel, Generic[T]):
    items: list[T]; total: int; page: int; size: int
```

```python
# miles_common/response.py
from miles_common.schema import ApiResponse, PageResult
from miles_common.trace import get_trace_id

def ok(data=None, message="ok", code=0) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=data, trace_id=get_trace_id())

def page_ok(items, total, page, size) -> ApiResponse[PageResult]:
    return ok(PageResult(items=items, total=total, page=page, size=size))
```

```python
# miles_common/exceptions.py
class AppError(Exception):
    def __init__(self, message, *, code=None, status_code=400):
        self.message = message
        self.status_code = status_code
        self.code = code if code is not None else status_code
        super().__init__(message)

class BadRequestError(AppError):
    def __init__(self, message="请求参数错误"): super().__init__(message, status_code=400)
class UnauthorizedError(AppError):
    def __init__(self, message="未授权"): super().__init__(message, status_code=401)
class ForbiddenError(AppError):
    def __init__(self, message="无权访问"): super().__init__(message, status_code=403)
class NotFoundError(AppError):
    def __init__(self, message="资源不存在"): super().__init__(message, status_code=404)
class ConflictError(AppError):
    def __init__(self, message="资源冲突"): super().__init__(message, status_code=409)
```

**要点**：业务代码**只抛** `AppError` 子类，绝不散落 `HTTPException`；处理器统一映射 JSON 信封。

```python
# miles_core/web/handlers.py（全局异常处理器注册）
exception_handlers = {
    RequestValidationError: validation_error_handler,   # 422
    AppError: app_error_handler,                        # 映射 status_code
    SQLAlchemyError: sqlalchemy_error_handler,          # 500 + 泛化文案
    Exception: unhandled_error_handler,                 # 500 + 隐藏细节
}
```

**要点**：`_public_message` 按 `debug` 决定是否暴露细节；生产环境对 `SQLAlchemyError` 给「数据库结构未同步」类可操作提示，而非裸 stacktrace。

### 4.4 认证与依赖注入（`core/security.py` + `core/deps.py`）

```python
# core/security.py —— JWT + bcrypt
def hash_password(p: str) -> str: ...   # bcrypt
def verify_password(plain, hashed) -> bool: ...
def create_access_token(subject, extra=None) -> str: ...  # type=access + jti + exp
def create_refresh_token(subject) -> str: ...             # type=refresh
def safe_decode_token(token) -> dict | None: ...          # 失败返回 None
```

```python
# core/deps.py —— FastAPI 依赖
bearer_scheme = HTTPBearer(auto_error=False)

async def get_page_params(page=1, size=10) -> PageParams: ...

async def get_current_user(credentials=Depends(bearer_scheme), db=Depends(get_db)) -> User:
    # decode → 校验 type == "access" → 查黑名单 → 查活跃用户 → touch session

async def get_tenant_context(user=Depends(get_current_user), credentials=Depends(bearer_scheme)) -> TenantContext:
    # 聚合 user.roles[].permissions → TenantContext

def require_permissions(*required: str):
    async def checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        ctx.require_permission(*required)
        return ctx
    return checker

def require_superuser(): ...
```

**要点**：权限在路由上用 `Depends(require_permissions("tag:write"))` 声明式注入；`TenantContext` 是请求级身份快照（见 4.5）。

### 4.5 多租户隔离（`core/tenant.py`）

```python
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    username: str
    is_superuser: bool
    permissions: frozenset[str]

    def has_permission(self, *codes) -> bool:
        return self.is_superuser or all(c in self.permissions for c in codes)

    def require_permission(self, *codes) -> None:
        if not self.has_permission(*codes):
            raise ForbiddenError(f"缺少权限: {', '.join(codes)}")

def assert_tenant_access(ctx, resource_tenant_id: UUID) -> None:
    """非超管只能访问自身租户资源。"""
    if not ctx.is_superuser and resource_tenant_id != ctx.tenant_id:
        raise ForbiddenError("无权访问该租户资源")

def tenant_filters(ctx, tenant_column, *, requested_tenant_id=None):
    """列表查询的租户过滤条件；超管可传 requested_tenant_id 跨租户查看。"""
    if ctx.is_superuser:
        return [tenant_column == requested_tenant_id] if requested_tenant_id else []
    return [tenant_column == ctx.tenant_id]
```

**要点**：**每个** Service 的列表/详情查询都要拼 `tenant_filters`，**每个** 按 ID 读资源后都要 `assert_tenant_access`。这是多租户安全的最后一道闸，缺一即水平越权。

### 4.6 软删除（`core/soft_delete.py`）与仓储/服务基类

```python
# core/soft_delete.py
def has_soft_delete(model) -> bool: return hasattr(model, "deleted_at")
def not_deleted(model): return model.deleted_at.is_(None)
def append_not_deleted(filters, model): ...
async def mark_deleted(db, entity): entity.deleted_at = utc_now(); await db.flush()
async def mark_deleted_where(db, model, *filters): ...  # 批量软删
```

```python
# core/repository.py —— 泛型 CRUD，默认排除软删行
class BaseRepository(Generic[T]):
    def __init__(self, db: AsyncSession, model: type[T]): ...
    async def get_by_id(self, entity_id, *, include_deleted=False) -> T | None: ...
    async def get_by_id_or_raise(self, entity_id, *, label=None) -> T: ...
    async def list_page(self, *, page, size, filters=None, order_by=None) -> PageResult[T]: ...
    async def create(self, **fields) -> T: ...
    async def soft_delete(self, entity) -> None: ...
    async def ensure_unique(self, field, value, *, message, exclude_id=None) -> None: ...
```

```python
# core/service.py
class BaseService:
    def __init__(self, db: AsyncSession, ctx: TenantContext | None = None):
        self.db = db
        self.ctx = ctx
```

**要点**：`list_page` 内部已带软删过滤；`ensure_unique` 抛 `ConflictError`；`flush()` 不 `commit`，事务由 `get_db` 收尾（见 4.7）。

### 4.7 数据库会话（`infra/db/async_session.py`）

```python
# infra/db/async_session.py —— engine 不暴露为模块级单例：由 loop 感知注册表（_loop_engines，
# WeakKeyDictionary 以事件循环为键）内部按 loop 持有，调用方无需（也无法）自己拿 engine。
def build_engine(settings: Settings) -> AsyncEngine: ...   # 池参数来自 Settings，注册表内部调用
def get_engine() -> AsyncEngine: ...                       # 当前 loop 的 engine（缺失即懒建）
def AsyncSessionLocal() -> AsyncSession: ...               # 当前 loop 的会话，写法与旧 sessionmaker 一致

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()      # 请求正常结束统一 commit
        except Exception:
            await session.rollback()    # 异常回滚
            raise
```

**要点**：Service/Repository 只 `flush`，**不** `commit`；请求边界由 `get_db` 统一提交/回滚。**engine 按事件循环持有**（见 MilesAi `infra/db/async_session` 的 `_loop_engines`）：Celery 任务每次 `asyncio.run` 都换 loop，复用绑在旧 loop 上的连接池会抛 `got Future attached to a different loop`，故取会话一律走同一个 loop 感知的工厂，Worker 无需另建会话类型。

### 4.8 敏感字段加密（`core/field_crypto.py`）

```python
# Fernet，密钥从 SECRET_KEY 派生（sha256 → base64）
def encrypt_secret(plain: str) -> str: ...
def decrypt_secret(cipher: str) -> str: ...
def mask_secret(value: str | None, *, visible_tail=4) -> str | None: ...  # 响应脱敏
```

**用途**：模型 API Key、对象存储 AK/SK 等，落库加密、返回时脱敏。

### 4.9 日志与 trace（`core/logging.py` + `middlewares/trace.py`）

- `setup_logging()`：幂等 `dictConfig`，统一控制 uvicorn / sqlalchemy / celery / litellm 级别；`get_logger(__name__)` 首次自动初始化。
- `TraceMiddleware`：读/生成 `X-Trace-Id` → 写 `request.state.trace_id` + `ContextVar` → 响应头回传。所有错误信封携带该 `trace_id` 便于排障。

---

## 5. 业务域开发模板（四件套 + 注册）

以「新增一个 `{domain}` 资源」为例，完整闭环如下。以下 `tag` 是 MilesAi 的真实最小示例，可直接替换为任意 CRUD 资源。

### 5.1 views（薄路由）

```python
# miles_portal/tenant/{domain}/views/{resource}.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from miles_common.response import ok
from miles_core.deps import require_permissions
from miles_core.tenant import TenantContext
from miles_core.infra.db import get_db
from miles_portal.tenant.{domain}.schemas.item import ItemCreate, ItemOut
from miles_portal.tenant.{domain}.services.item import ItemService

router = APIRouter()

def _svc(db: AsyncSession, ctx: TenantContext) -> ItemService:
    return ItemService(db, ctx)

@router.get("", response_model=ApiResponse[list[ItemOut]])
async def list_items(
    ctx: TenantContext = Depends(require_permissions("{domain}:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_items())

@router.post("", response_model=ApiResponse[ItemOut])
async def create_item(
    body: ItemCreate,
    ctx: TenantContext = Depends(require_permissions("{domain}:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_item(body))

@router.delete("/{item_id}", response_model=ApiResponse[None])
async def delete_item(
    item_id: UUID,
    ctx: TenantContext = Depends(require_permissions("{domain}:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_item(item_id)
    return ok(message="已删除")
```

### 5.2 schemas

```python
# miles_portal/tenant/{domain}/schemas/item.py
class ItemOut(BaseModel):
    id: UUID; tenant_id: UUID; name: str; created_at: datetime
    model_config = {"from_attributes": True}   # 支持 ORM 对象直接 validate

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
```

### 5.3 services（业务逻辑 + 租户校验）

```python
# miles_portal/tenant/{domain}/services/item.py
class ItemService(BaseService):
    async def list_items(self) -> list[ItemOut]:
        stmt = select(Item).where(*tenant_filters(self.ctx, Item.tenant_id), not_deleted(Item)).order_by(Item.name.asc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [ItemOut.model_validate(r) for r in rows]

    async def create_item(self, body: ItemCreate) -> ItemOut:
        # 唯一性校验 → ConflictError；写库 → flush + refresh
        ...

    async def delete_item(self, item_id: UUID) -> None:
        row = await self.db.get(Item, item_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("资源不存在")
        assert_tenant_access(self.ctx, row.tenant_id)   # 防水平越权
        await mark_deleted(self.db, row)
```

### 5.4 路由注册（`tenant/router.py`）

```python
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(items.router, prefix="/{domain}", tags=["{domain}"])
```

**一个域从零到可用的 Checklist**：

1. `models.py`（若有域私有表）→ 登记到 `models/registry.py` 的 `load_all_models()`。
2. `schemas/` 定义 DTO。
3. `services/` 写用例（带租户校验）。
4. `views/` 写薄路由（带权限依赖）。
5. `tenant/router.py` include。
6. `meta.py` 提供枚举字典（若需要 `GET /{domain}/meta`）。
7. 种子写入 `scripts/seed/`。
8. 补 `tests/tenant/{domain}/`。

---

## 6. ORM 与数据库约定

### 6.1 模型 Mixin（`models/base.py`）

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
```

**主键用 UUIDv7**（时间有序，利于 B-tree / 向量索引），见 `utils/idgen.py`。

### 6.2 表名域前缀 + 索引命名 + 逻辑外键

| 约定 | 规则 | 示例 |
|------|------|------|
| 表名前缀 | 每域固定前缀 | `sys_` 系统 / `{domain}_` 业务 |
| 单列索引 | `idx_{table}_{col}` | `idx_sys_users_tenant_id` |
| 唯一约束 | `uk_{table}_{col}` | `uk_sys_users_username` |
| 联合非唯一 | `un_{table}_{cols}` | — |
| 外键 | **不建** DB 级 `FOREIGN KEY` | 列用 UUID，`relationship(foreign_keys=..., primaryjoin=...)` |

**要点**：逻辑外键 + 应用层 `cascade`；级联删除由 `deletion/` 编排模块保证顺序（无 DB 约束时）。

```python
class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sys_users"
    __table_args__ = (
        Index("idx_sys_users_tenant_id", "tenant_id"),
        UniqueConstraint("username", name="uk_sys_users_username"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_roles, back_populates="users")
```

### 6.3 ORM 登记（`models/registry.py`）

```python
def load_all_models() -> None:
    import miles_core.models.platform  # noqa: F401
    import miles_core.models.{domain}  # noqa: F401
    ...
```

**要点**：不要在 `models/__init__.py` 反向 import `admin`（循环引用）；新增 ORM 模块后在此补一行 import，供 Alembic `create_all` 收集 metadata。

### 6.4 Alembic 策略

- 只保留 `001_initial_schema.py`（按 ORM metadata 一次性 `create_all`），后续大改为增量版本。
- **启动期**：API lifespan 调 `alembic upgrade head`（`apps/migrate.py`）。
- **种子**：CLI `init-db` 显式写入，API 启动**不**自动写种子。
- **契约快照**：`python -m miles_server.scripts.export_openapi --check` 比对 `openapi.snapshot.json`，CI 校验，防 API 漂移。

---

## 7. 基础设施抽象层（协议 + 工厂）

**原则**：业务代码只依赖**协议门面**，不依赖具体 SDK 实现；实现可切换。

```text
业务层 ──► 门面/工厂（get_object_storage() / get_vector_store()）
                │
                ├── S3 兼容实现（MinIO / OSS / AWS S3）
                ├── Weaviate / Milvus / pgvector 适配器
                └── 预留其它实现
```

### 7.1 门面优于直接调客户端

```python
# infra/storage/base.py —— Protocol（运行时校验）
@runtime_checkable
class ObjectStorage(Protocol):
    def upload_bytes(self, data: bytes, object_key: str, content_type: str, bucket=None) -> None: ...
    def download_bytes(self, object_key: str, bucket=None) -> bytes: ...
    def delete_object(self, object_key: str, bucket=None) -> None: ...
    def health_check(self) -> bool: ...

# infra/storage/factory.py
def get_object_storage() -> ObjectStorage: ...  # 按 OBJECT_STORAGE_BACKEND 返回实现
```

```python
# infra/vector_store/base.py —— 存储 DTO + 协议
@dataclass(frozen=True)
class ChunkVectorRecord:
    vector: list[float]; tenant_id: UUID; kb_id: UUID; document_id: UUID
    chunk_id: UUID; content_preview: str; object_key: str; page_no: int | None = None

@runtime_checkable
class VectorStore(Protocol):
    def ensure_schema(self, dimension: int) -> None: ...
    def upsert_chunk(self, record: ChunkVectorRecord) -> str: ...
    def search(self, query_vector, *, tenant_id, kb_id=None, limit=10) -> list[dict]: ...
    def delete_by_document(self, document_id) -> None: ...
```

**要点**：
- 向量/对象**引擎类型**由部署级环境变量全局决定，**不做** per-tenant 多引擎混用（运维复杂、检索不可跨库）。
- 多租户隔离靠**元数据 Filter**（`tenant_id`/`kb_id`）与对象 key 前缀，而不是每租户一套引擎。
- 检索策略（hybrid/RRF）与 prompt 拼装属**领域逻辑**，放在 `rag/retrieve`、`rag/generate`，**不**下沉到 `infra`。

### 7.2 Redis 客户端（`infra/redis/client.py`）

```python
def get_redis() -> aioredis.Redis:
    # 按当前事件循环缓存实例；loop 变化（Celery asyncio.run）时重建
    # 否则触发 "Future attached to a different loop"
```

---

## 8. 异步任务（Celery）

```python
# miles_worker/app.py
celery_app = Celery("myapp", broker=settings.celery_broker_url,
                    backend=settings.celery_result_backend, include=["miles_worker.tasks"])
celery_app.conf.update(
    task_track_started=True, task_acks_late=True,
    worker_prefetch_multiplier=1,                 # 长任务避免抢占
    task_soft_time_limit=..., task_time_limit=...,
    task_routes={"milesai.tasks.ingest.*": {"queue": "parse"}},  # 按任务分流队列；协议名见 TASK_NAMES
    beat_schedule={"tick-schedules": {"task": "...", "schedule": 60.0}},  # 定时
)
```

**要点**：
- 长任务（入库、生成）**必须**异步化，队列区分（`parse` / `default` / 预留扩展）。
- 任务表（`task_records`）记录 Celery 状态，供「任务中心」查询/取消/重试。
- 任务内直接取 loop 感知的会话工厂（engine 按事件循环持有），复用绑在旧 loop 上的 engine 会踩 event loop 坑。
- Beat 是**独立进程**，不要与 Worker 混跑。

---

## 9. 规范与护栏（写进 `.cursorrules` / `AGENTS.md`）

这些约束是项目可长期维护的关键，建议固化到规则文件：

| 护栏 | 阈值/规则 |
|------|-----------|
| 单文件体量 | `backend/packages/*/src/` 下业务 `.py` **≥ 500 行禁止合入**，按职责拆子包/子文件；拆分后宜 300–400 行 |
| services 子包聚合 | 单个 Service 超 500 行或 Mixin 增多时，拆 `services/{aggregate}/` + `service.py` 门面 + `__init__.py` 唯一导出 |
| docstring | 模块/类/公开方法/模块级函数必须有**中文 docstring**；禁止无信息量的 `#` 注释 |
| import 方向 | 严格 L0→L4；`infra`/`integrations` 不得 import `tenant`；同级域不互 import 内部文件 |
| 常量分家 | `models.Enum` 为持久化真源；`{domain}/meta.py` 仅 label/hint；Redis 键集中 `miles_common/redis_keys.py` |
| 类型 | 跨层优先 `@dataclass`/`TypedDict`，少用裸 `dict[str, Any]` |
| 异常 | 只抛 `AppError` 子类；不散落 `HTTPException` |
| 事务 | Service 只 `flush`，`get_db` 统一 commit/rollback |

**自检命令**：

```bash
cd backend
find packages -path '*/src/*' -name '*.py' -exec wc -l {} + | awk '$1 >= 500'   # 找出超标文件
python -m miles_server.scripts.export_openapi --check                           # 契约漂移校验
```

---

## 10. 快速搭建 Checklist（给 LLM 的执行清单）

按顺序执行，完成后即得到一个可运行的骨架：

- [ ] 1. 建目录树（§3），补齐各层 `__init__.py`。
- [ ] 2. uv workspace 根 `pyproject.toml` 声明 `[dependency-groups].dev` 与成员；`miles-server` 声明 `[project.scripts] milesai = "miles_server.cli:main"`。
- [ ] 3. 落地 `miles_core`（config、security、deps、tenant、repository、service、soft_delete、field_crypto、logging）。
- [ ] 4. 落地 `miles_common`（response、exceptions、schema、trace）+ `miles_core/`（`web/handlers.py`、`pagination.py`）。
- [ ] 5. 落地 `infra/db`（loop 感知的 engine + `get_db`）。
- [ ] 6. 落地 `models/`（base Mixin + 核心表）+ `miles_server/registry.py`。
- [ ] 7. 落地 `miles_server/apps/`（`application.py` 工厂、`migrate.py`）+ `main.py`；域 API 经 `register_portal` / `register_admin` / `register_open` 装配；`miles_core/web/middlewares/`。
- [ ] 8. `alembic` 初始化 + `001_initial_schema`；`milesai init-db` 写入种子账号。
- [ ] 9. 落地 `miles_worker/`（Celery app + 至少一个任务）+ Beat 配置。
- [ ] 10. 按 §5 模板实现**第一个域**（auth 或 system），验证「登录 → 权限 → 租户隔离 → 软删 → 分页」闭环。
- [ ] 11. 如需 RAG/编排，按 §2.2 分层接入 `miles_ai/` 的 `rag/`、`integrations/`、`flow_runtime/`。
- [ ] 12. `python -m miles_server.scripts.export_openapi --write` 生成契约快照；补测试。

---

## 11. 认证、会话与权限（进阶）

§4.4 给了最小 JWT 骨架，本节补全「企业级」需要的三件事：双 token、多端会话、RBAC。

### 11.1 双 Token + jti 黑名单

```python
# access：短时效，type=access，extra 携带 tenant_id / is_superuser
def create_access_token(subject, extra=None, *, expires_delta=None) -> str:
    payload = {"sub": subject, "type": "access", "exp": expire, "jti": str(uuid4()), **(extra or {})}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

# refresh：仅用于换取新 token，type=refresh
def create_refresh_token(subject) -> str:
    payload = {"sub": subject, "type": "refresh", "exp": expire, "jti": str(uuid4())}
    ...
```

**关键设计**：
- `jti`（JWT ID）是每个令牌的唯一标识，用于**黑名单**与**多端会话追踪**。
- `type` 字段区分 access/refresh，鉴权时强校验 `payload.get("type") == "access"`，防止用 refresh 冒充 access。
- `safe_decode_token` 失败返回 `None`（而非抛异常），供 `get_current_user` 区分「无效令牌」与「有效但需进一步校验」。

**登出/踢人流程**：

```python
async def blacklist_token(access_token: str) -> None:
    payload = safe_decode_token(access_token)
    jti, exp = payload.get("jti"), payload.get("exp")
    # TTL 精确到令牌剩余有效期，避免黑名单无限膨胀
    ttl = max(60, int(exp - now.timestamp()))
    await redis.setex(RedisKeys.token_blacklist(jti), ttl, "1")
```

### 11.2 多设备会话（Redis SET + 哈希）

每用户用 Redis **SET 索引**记录所有在线 `jti`，每个 `jti` 对应一条 JSON 元数据（设备、IP、时间）：

```python
# 登录/刷新后登记
await redis.setex(f"session:entry:{user_id}:{jti}", TTL, json.dumps(meta))   # 单条元数据
await redis.sadd(f"sessions:user:{user_id}", jti)                             # 会话索引

# 列表 / 下线单设备 / 下线其它设备
async def revoke_all_sessions(user_id, *, keep_jti=None) -> int:
    for jti in await redis.smembers(index_key):
        if keep_jti and jti == keep_jti: continue
        await redis.setex(f"token:blacklist:{jti}", TTL, "1")   # 拉黑
        await redis.delete(entry_key); await redis.srem(index_key, jti)
```

**鉴权时顺带「续期」**：`touch_session` 在每次通过鉴权后刷新 `last_seen_at`（轻量，可后端限流跳过）。

### 11.3 RBAC 权限模型

```text
sys_users ──user_roles──> sys_roles ──role_permissions──> sys_permissions(code)
```

- 权限码约定 `domain:action`，如 `tag:read`、`tag:write`、`kb:read`、`attachment:upload`、`marketplace:review`。
- 路由声明式注入：`Depends(require_permissions("tag:write"))`；`require_superuser()` 用于基础设施探测等仅超管接口。
- `TenantContext.has_permission`：**超管恒为 True**；`get_me` 返回 `["*"]` 表示全量权限。
- **meta 端点约定**：`GET /{module}/meta` 返回枚举展示字典（无 DB 查询，文案来自 `{domain}/meta.py`），供前端下拉/筛选渲染，与 RBAC 权限码是两套契约。

---

## 12. 审计日志

**写入与查询分离**：写用模块级函数（可无 `TenantContext`，如登录审计），读用 Service。

```python
# 写入（业务变更成功后调用；不 commit，由调用方会话收尾）
async def write_tenant_audit_log(db, ctx, *, action, resource_type=None,
                                 resource_id=None, request=None, detail=None) -> None:
    await TenantAuditLogRepository(db).create(
        tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        action=action, resource_type=resource_type, resource_id=resource_id,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent"),
        detail=detail or {},
    )

# 登录审计（无 ctx）
async def write_auth_login_audit(db, *, tenant_id, user_id, ip=None, user_agent=None) -> None:
    ...
```

**要点**：
- `action` 用点分命名（如 `auth.login`）；`resource_type`/`resource_id` 定位对象。
- 审计表 `append-only`（只 `created_at`/`updated_at`，**无** `deleted_at` 软删）。
- 列表聚合 username 时**避免 N+1**：先取本页 `user_id` 集合，一次 `IN` 查询映射。

---

## 13. 删除编排（无外键级联）

ORM 用**逻辑外键**（不建 DB `FOREIGN KEY`），因此级联删除由 `deletion/` 编排模块显式保证顺序，避免工作台/市场出现悬空引用。

**三种清理动作**：

| 动作 | 场景 | 示例 |
|------|------|------|
| `unlink`（删关联行） | M:N 绑定表 | `agent_kb_bindings`、`sub_agent_bindings` |
| `nullify`（置空引用） | 弱引用，可空 | 市场 `AppInstall.agent_id/flow_id/kb_id = NULL` |
| `clear`（清指针） | 单向外键 | 智能体 `published_flow_id = NULL` |

```python
async def before_delete_agent(db, agent_id) -> None:
    """删智能体前：解绑所有关联，再软删主行。"""
    await unlink_sub_agent_bindings(db, parent_agent_id=agent_id, child_agent_id=agent_id)
    await unlink_agent_kb_bindings(db, agent_id=agent_id)
    await nullify_app_install_refs(db, agent_id=agent_id)
    await delete_hook_bindings_for_target(db, HookScope.AGENT, agent_id)
    await mark_deleted_where(db, AgentSchedule, AgentSchedule.agent_id == agent_id)
    await db.execute(delete(AgentChatSession).where(AgentChatSession.agent_id == agent_id))
```

**约定**：每个「删主资源」的 Service 方法先调对应 `before_delete_*`，再 `mark_deleted` 主行；文档类资源需先逐条清衍生数据（向量/对象存储/分片）再删。

---

## 14. 长任务状态机与流式进度

### 14.1 任务记录表（DB 与 Celery 状态对账）

```text
CeleryTaskRecord: tenant_id, celery_task_id, task_name,
                  status(PENDING/RUNNING/SUCCESS/FAILED/CANCELLED),
                  resource_type, resource_id, fail_reason, created_by
```

- **投递时**：`create_record` 写入 `PENDING`，`celery_task_id` 关联 Celery 任务。
- **Worker 内**：任务执行时 `sync_task_by_celery_id` 更新状态与 `fail_reason`。
- **查询时**：`get_task` 用 `AsyncResult(celery_task_id)` 对 DB 状态**纠偏**（DB 可能滞后），仅对 `PENDING/RUNNING` 记录做映射，失败不影响返回。

### 14.2 取消 / 重试 / 批量

```python
async def cancel_task(self, task_id) -> TaskRecordOut:
    record = await self._get_record_or_raise(task_id)
    if record.status in (SUCCESS, CANCELLED): raise BadRequestError("任务已结束，无法取消")
    celery_app.control.revoke(record.celery_task_id, terminate=True)
    record.status = CANCELLED; await self.db.flush()

async def batch_cancel_tasks(self, task_ids) -> BatchCancelResult:
    # 单条失败不中断：NotFound / 已结束 → skipped；成功 → cancelled
```

**要点**：`_get_record_or_raise` 支持 UUID 主键 **或** `celery_task_id` 双键查询，且必经 `assert_tenant_access`。

### 14.3 SSE 进度流

```python
@router.get("/{job_id}/stream")
async def stream_generative_job(job_id: UUID, ctx=Depends(require_permissions("attachment:read")), db=Depends(get_db)):
    gen = _svc(db, ctx).stream_job_events(job_id)
    async def body():
        async for chunk in gen: yield chunk
    return StreamingResponse(body(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
```

**要点**：`X-Accel-Buffering: no` 关闭 nginx 缓冲，保证事件实时推送；进度可用 Redis Pub/Sub 频道（`generative:job:{tenant_id}:{job_id}`）跨进程广播。

---

## 15. 运行时切面与安全风控

### 15.1 Hook 切面（before / after）

在智能体对话、流程运行、工具调用等执行路径挂载可扩展切面，不硬编码业务：

```python
class HookRunner:
    def __init__(self, db, tenant_id): self._executor = HookExecutor(db, tenant_id)
    async def run(self, trigger, scope, target_id, payload) -> HookRunResult:
        return await self._executor.run(trigger=trigger, scope=scope, target_id=target_id, payload=payload)
```

- **trigger**：`BEFORE_CALL` / `AFTER_CALL` / `BEFORE_TOOL` / `AFTER_TOOL` 等。
- **效果**：`block`（拦截）/ `modify`（改写 payload）；`on_failure` 策略 `ignore` | `fail_request`。
- **挂载点**：Agent chat 入参/出参、Flow run、工具 `invoke_tool_with_context`。
- 设计原则：**切面是插件位，业务主链不感知**；钩子失败是否影响主流程由策略决定。

### 15.2 风控中间件（IP 黑名单 + 限流）

```python
class PlatformRiskMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if _should_skip(path): return await call_next(request)   # /health /docs 等白名单
        ip = _client_ip(request)                                  # 优先 x-forwarded-for
        if await enforcer.is_ip_blocked(ip): return 403
        if path.startswith("/api/v1"):
            limited, rule_id = await enforcer.check_rate_limit(path, ip)
            if limited: return 429
        return await call_next(request)
```

**要点**：限流/黑名单命中时写 `risk_event` 供运营审计；白名单前缀跳过健康检查与文档，避免误伤。

### 15.3 安全清单（可作 code review 检查项）

| 项 | 落地 |
|----|------|
| 敏感字段加密 | Fernet（密钥派生自 `SECRET_KEY`）存模型 API Key / 对象存储 AK |
| 响应脱敏 | `mask_secret(value, visible_tail=4)` 返回掩码 |
| SSRF 防护 | MCP/HTTP 出站默认禁止连本机/内网（`MCP_ALLOW_PRIVATE_HOSTS=false` 生产） |
| 越权防护 | 每个读/改操作必经 `assert_tenant_access` + `tenant_filters` |
| 水平越权兜底 | `resolve_tenant_id` 非超管只能访问自身租户 |
| 令牌失效 | jti 黑名单 + 多端会话可踢下线 |
| 调试泄漏 | `debug=False` 固定写死，生产隐藏错误细节 |

---

## 16. 测试策略

分层测试，`rag` 单测不启动 FastAPI，向量库测试 mock `get_vector_store`。

```python
# conftest.py —— 依赖覆盖 + ASGI 内存客户端
@pytest.fixture
def api_app():
    app = create_app()
    ctx = make_tenant_ctx()                 # 构造 TenantContext
    app.dependency_overrides[get_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def api_client(api_app):
    transport = ASGITransport(app=api_app)  # 无需真实启动 uvicorn
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

**要点**：
- `ASGITransport` 直连 ASGI app，测试不依赖真实端口/中间件。
- 风控等中间件用 `patch` 绕过（避免测试依赖 Redis）。
- `make_tenant_ctx` 可注入任意 `permissions`，便于测 RBAC 分支。
- 目录组织：`tests/{api,integration,rag,flow,tenant/{domain},mcp,admin,infra}`，`conftest.py` + `paths.py` 提供 `BACKEND_ROOT`。

---

## 17. 常见反模式与坑

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| Worker 复用绑在旧 loop 上的 async engine | `Future attached to a different loop` | engine 按事件循环持有，Worker 与 API 共用同一个循环感知的会话工厂 |
| Redis 客户端跨 event loop 缓存 | 同上 | `get_redis()` 按 `id(loop)` 判断重建 |
| `debug=True` 传给 FastAPI | 明文 traceback 绕过统一信封 | `create_app` 固定 `debug=False` |
| 忘 `tenant_filters` / `assert_tenant_access` | 水平越权 | 列表/详情查询两处都必须有 |
| Service 里 `commit` | 破坏请求边界事务 | 只 `flush`，`get_db` 统一 commit/rollback |
| 散落 `HTTPException` | 信封不一致 | 只抛 `AppError` 子类 |
| 大文件不拆 | 单文件 >500 行难以维护 | 按 §9 拆子包/子文件 |
| 列表逐条查 username | N+1 查询 | 一次 `IN` 查询批量映射 |
| 魔法字符串散落 | key 冲突难排 | 集中 `miles_common/redis_keys.py` / `constants.py` |
| 向量/对象引擎 per-tenant 混用 | 运维复杂、检索不可跨库 | 全局环境变量定引擎，隔离靠 Filter |

---

## 附：本框架对应的 MilesAi 落点（对照阅读）

| 框架条目 | MilesAi 实际路径 |
|----------|------------------|
| 应用装配 | `backend/packages/miles-server/src/miles_server/apps/application.py`、`main.py` |
| 配置 | `backend/packages/miles-core/src/miles_core/config.py` |
| 统一信封/异常 | `backend/packages/miles-common/src/miles_common/{response,exceptions,schema}.py`、`miles-core/src/miles_core/web/handlers.py` |
| 依赖注入/权限 | `backend/packages/miles-core/src/miles_core/{deps,security,tenant}.py` |
| 仓储/服务基类 | `backend/packages/miles-core/src/miles_core/{repository,service,soft_delete}.py` |
| ORM Mixin | `backend/packages/miles-core/src/miles_core/models/base.py`、`miles-server/src/miles_server/registry.py` |
| 对象/向量抽象 | `backend/packages/miles-core/src/miles_core/infra/{storage,vector_store}/` |
| 域模板最小示例 | `backend/packages/miles-portal/src/miles_portal/tenant/tags/` |
| Celery | `backend/packages/miles-worker/src/miles_worker/app.py` |
| 认证/会话 | `backend/packages/miles-portal/src/miles_portal/tenant/auth/services/auth.py`、`miles-core/src/miles_core/auth/session_store.py` |
| RBAC | `backend/packages/miles-core/src/miles_core/{deps,tenant}.py`、`miles-core/src/miles_core/models/platform/role.py` |
| 审计 | `backend/packages/miles-portal/src/miles_portal/tenant/audit_log/services/audit_log.py` |
| 删除编排 | `backend/packages/miles-portal/src/miles_portal/deletion/{cascade,document,tenant}.py` |
| 任务状态机 | `backend/packages/miles-portal/src/miles_portal/tenant/tasks/services/task.py`、`miles-core/src/miles_core/models/task/task_record.py` |
| SSE 进度 | `backend/packages/miles-portal/src/miles_portal/tenant/generative/views/jobs.py` |
| Hook 切面 | `backend/packages/miles-portal/src/miles_portal/tenant/hooks/services/{runner,executor,result}.py` |
| 风控中间件 | `backend/packages/miles-core/src/miles_core/web/middlewares/platform_risk.py` |
| Redis Key 集中管理 | `backend/packages/miles-common/src/miles_common/redis_keys.py` |
| 大服务 Mixin 门面 | `backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/{service,__init__}.py` |
| 可选能力降级 | `backend/packages/miles-ai/src/miles_ai/integrations/langgraph/checkpointer.py` |
| 测试 fixture | `backend/tests/conftest.py` |
| 分层规范原文 | `docs/architecture/layering.md` |
| As-Is 架构总纲 | `docs/architecture/technical-design.md` |
