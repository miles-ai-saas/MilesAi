# A2A 专用限流与审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 A2A 对外端点加上「按 API Key 计量的限流」与「按调用留痕的租户审计」，超限回 HTTP 429 + `Retry-After` + JSON-RPC 错误信封。

**Architecture:** 复用既有平台风控设施（`adm_rate_limit_rules` + `PlatformRiskEnforcer` 的 Redis 固定窗口 + `RiskEvent`），只给它加一个 `scope` 维度（`ip` / `api_key`）；审计复用租户流水 `aud_logs`（`write_tenant_audit_log`），但**走独立会话**写入，避免业务回滚吞掉留痕。检查点在 A2A 视图内、鉴权之后（此时才拿得到可信的 Key 身份）。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2 / Redis / pytest（`asyncio_mode = "auto"`）/ Next.js 14 + React 18（运营后台）。

设计来源：`docs/superpowers/specs/2026-09-20-a2a-rate-limit-audit-design.md`（已批准）。

## Global Constraints

- 所有提交的 subject/body **必须简体中文**，格式 `<type>(<scope>): <简述>`，说明「为什么」而非罗列文件名。
- 后端质量门：`make lint-backend format-check-backend layers-check openapi-check test-backend`（等价 `make check`）。
- 分层契约（`backend/.importlinter`）：`miles_openapi` / `miles_portal` / `miles_core` 自上而下单向依赖；**`views/` 与 `schemas/` 不得直接 import ORM 模块**（`miles_core.models`、`miles_admin.models` 等）。故 `scope` 在 API 侧一律用 `Literal` 表达，不得引入 ORM 枚举类。
- 枚举契约（`backend/tests/models/test_enum_contract.py`）：`_UP042_ENUMS` 的 **22 模块 / 32 枚举 / 134 成员**计数已冻结。本批新增的 `RateLimitScope` 是**新的** `StrEnum`、不属于 UP042 迁移清单，**不得**加进该表（加进去会让 33 != 32 断言失败）。
- 宽泛 `except` 守卫（`backend/tests/test_no_silent_broad_except.py`）：`except Exception` 必须记日志（`logger.exception` 或带 `exc_info=True`）或重抛，不得静默。
- 运行单个测试：`cd backend && uv run python -m pytest -q <路径>::<用例名>`（**不要**用 `uv run pytest tests/...`，会因 `tests` 非包而 `ModuleNotFoundError`）。
- 前端质量门：`make check-ui`（`lint-ui` + `format-check-ui`）。UI 仓**无测试运行器**，故前端任务的验证步骤是类型/风格门禁，不写单测。
- 超限错误码 `-32000` 落在 A2A 规范的「实现自定义」区间（`-32000..-32099`），且必须写进 `docs/guides/a2a.md`（规范要求自定义码「清楚地记录」）。

---

### Task 1: 核心限流——`scope` 维度与命中信息

给规则表加维度、让 `check_rate_limit` 只认同维度规则并回传 `Retry-After` 所需的剩余秒数。四个文件必须**同一次**改完：签名一改，中间件与 `conftest` 的替身会立刻失配。

**Files:**
- Modify: `backend/packages/miles-core/src/miles_core/models/risk.py`
- Modify: `backend/packages/miles-core/src/miles_core/risk/enforce.py`
- Modify: `backend/packages/miles-core/src/miles_core/web/middlewares/platform_risk.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/admin/test_admin_risk_enforce.py`
- Create: `backend/alembic/versions/003_adm_rate_limit_rules_scope.py`

**Interfaces:**
- Consumes: 无（本任务是起点）。
- Produces:
  - `miles_core.models.risk.RateLimitScope`（`StrEnum`：`IP = "ip"`、`API_KEY = "api_key"`）
  - `miles_core.models.risk.RateLimitRule.scope: str`（列 `scope VARCHAR(16) NOT NULL DEFAULT 'ip'`）
  - `miles_core.risk.enforce.RateLimitHit(rule_id: UUID, limit_per_minute: int, retry_after_seconds: int)`
  - `PlatformRiskEnforcer.check_rate_limit(path: str, client_key: str, *, scope: RateLimitScope) -> RateLimitHit | None`
  - `miles_core.web.middlewares.platform_risk.client_ip(request: Request) -> str`

- [ ] **Step 1: 写失败测试（维度过滤 + 命中信息 + 桶隔离）**

`backend/tests/admin/test_admin_risk_enforce.py` 全文替换为：

```python
"""平台风控运行时单元测试。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_core.models.risk import RateLimitScope
from miles_core.risk import enforce as enforce_mod
from miles_core.risk.enforce import PlatformRiskEnforcer


class _FakeRedis:
    """只实现 ``check_rate_limit`` 用到的两条命令的固定窗口替身。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True


class _RiskDb:
    """``_ensure_cache`` 的会话替身：第一次 ``execute`` 取 IP 黑名单（空），第二次取规则。"""

    def __init__(self, rules: list[object]) -> None:
        self._batches: list[list[object]] = [[], rules]

    async def __aenter__(self) -> "_RiskDb":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, _stmt: object) -> object:
        rows = self._batches.pop(0) if self._batches else []
        return SimpleNamespace(scalars=lambda: iter(rows))


def _rule(*, scope: str, limit: int = 1, pattern: str = "/api/v1/open/a2a/*") -> object:
    return SimpleNamespace(id=uuid4(), path_pattern=pattern, limit_per_minute=limit, scope=scope)


def _enforcer(monkeypatch, rules: list[object], redis: _FakeRedis) -> PlatformRiskEnforcer:  # noqa: ANN001
    monkeypatch.setattr(enforce_mod, "AsyncSessionLocal", lambda: _RiskDb(rules))
    monkeypatch.setattr(enforce_mod, "get_redis", lambda: redis)
    return PlatformRiskEnforcer()


def test_match_path_wildcard():
    enforcer = PlatformRiskEnforcer()
    assert enforcer._match_path("/api/v1/*", "/api/v1/auth/login") is True
    assert enforcer._match_path("/api/v1/*", "/api/admin/v1/tenants") is False


@pytest.mark.asyncio
async def test_scope_filters_rules_by_dimension(monkeypatch):  # noqa: ANN001
    """一条 ip 规则不参与 api_key 维度的计数：两个维度各自独立分桶。"""
    rule = _rule(scope="ip", limit=1)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    for _ in range(3):
        assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None


@pytest.mark.asyncio
async def test_api_key_scope_returns_hit_with_retry_after(monkeypatch):  # noqa: ANN001
    """超限时回命中信息，供调用方写 429 + ``Retry-After``。"""
    rule = _rule(scope="api_key", limit=2)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    hit = await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY)

    assert hit is not None
    assert hit.rule_id == rule.id
    assert hit.limit_per_minute == 2
    # 固定窗口剩余秒数：至少 1 —— 回 0 等于让对端立刻重试，比不回更糟
    assert 1 <= hit.retry_after_seconds <= 60


@pytest.mark.asyncio
async def test_buckets_are_per_client_key(monkeypatch):  # noqa: ANN001
    """一把 Key 超限不得连坐到另一把：轮换 Key / 多对端接入要靠这条成立。"""
    rule = _rule(scope="api_key", limit=1)
    enforcer = _enforcer(monkeypatch, [rule], _FakeRedis())

    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k2", scope=RateLimitScope.API_KEY) is None
    assert await enforcer.check_rate_limit("/api/v1/open/a2a/agents/x", "key:k1", scope=RateLimitScope.API_KEY) is not None
```

另在 `backend/tests/admin/test_audit_log_indexes.py` **之外**新建列形状断言——直接追加到本文件末尾（与索引守卫同思路，把列形状钉在模型上）：

```python
def test_scope_column_defaults_to_ip_for_backward_compatibility():
    """存量规则的语义不能变：新列默认 ``ip``，加了列之后它们仍按来源 IP 生效。"""
    from sqlalchemy import String

    from miles_core.models.risk import RateLimitRule

    column = RateLimitRule.__table__.c["scope"]
    assert isinstance(column.type, String)
    assert column.type.length == 16
    assert column.nullable is False
    assert column.default is not None and column.default.arg == "ip"
    assert column.server_default is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/admin/test_admin_risk_enforce.py`
Expected: FAIL —— `ImportError: cannot import name 'RateLimitScope' from 'miles_core.models.risk'`

- [ ] **Step 3: 规则表加 `scope` 列与维度枚举**

在 `backend/packages/miles-core/src/miles_core/models/risk.py` 的 `RiskSeverity` 之后插入：

```python
# 限流计量维度：一条规则只对同维度的流量生效。
# 刻意**不**用 SAEnum：本列只有两个取值、校验在应用层做，而 PG 原生枚举要 CREATE TYPE
# 并让 downgrade 变复杂；`RiskSeverity` 用 SAEnum 是因为它先于本列存在。
class RateLimitScope(enum.StrEnum):
    IP = "ip"
    API_KEY = "api_key"
```

在 `RateLimitRule` 的 `path_pattern` 之后插入：

```python
    scope: Mapped[str] = mapped_column(String(16), default=RateLimitScope.IP.value, server_default="ip", nullable=False)
```

- [ ] **Step 4: 加迁移**

创建 `backend/alembic/versions/003_adm_rate_limit_rules_scope.py`：

```python
"""adm_rate_limit_rules 增加 scope（限流计量维度）

Revision ID: 003
Revises: 002
Create Date: 2026-09-20

按 API Key 限流需要区分「这条规则算哪个维度」：A2A 对外端点要按调用方的 Key 计数，
而平台通用限流仍按来源 IP。默认 ``ip`` 是向后兼容的关键 —— 存量规则语义不变，
无需数据回填。

用 ``VARCHAR`` 而非 PG 原生枚举：本列只有两个取值、校验在应用层做，而枚举类型要
``CREATE TYPE`` 且拖累 ``downgrade``。``IF NOT EXISTS`` 沿用 002 的理由：新库经 001 的
``create_all`` 已按 ORM 建出该列，重复执行需为 no-op。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "adm_rate_limit_rules"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS scope VARCHAR(16) NOT NULL DEFAULT 'ip'")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS scope")
```

- [ ] **Step 5: `check_rate_limit` 加 scope 与命中信息**

在 `backend/packages/miles-core/src/miles_core/risk/enforce.py`：

顶部 import 区加 `import math`，并把 `from miles_core.models.risk import IpBlacklist, RateLimitRule, RiskEvent, RiskSeverity` 改为：

```python
from miles_core.models.risk import IpBlacklist, RateLimitRule, RateLimitScope, RiskEvent, RiskSeverity
```

在 `_RateRule` 加字段：

```python
@dataclass(frozen=True)
class _RateRule:
    id: UUID
    path_pattern: str
    limit_per_minute: int
    scope: str
```

在 `_RateRule` 之后加结果对象：

```python
@dataclass(frozen=True)
class RateLimitHit:
    """命中的限流规则与恢复时间（调用方据此回 429 + ``Retry-After``）。"""

    rule_id: UUID
    limit_per_minute: int
    retry_after_seconds: int
```

`_ensure_cache` 里构造规则处补 `scope`：

```python
        self._rate_rules = [
            _RateRule(id=r.id, path_pattern=r.path_pattern, limit_per_minute=r.limit_per_minute, scope=r.scope) for r in rule_rows
        ]
```

`check_rate_limit` 整体替换为：

```python
    async def check_rate_limit(self, path: str, client_key: str, *, scope: RateLimitScope) -> RateLimitHit | None:
        """按 ``scope`` 维度检查固定窗口；超限返回命中信息，否则 None。

        ``scope`` 是**必填关键字**：调用方必须显式声明自己算哪个维度 —— 否则将来新增
        调用方时会默默继承一个错的语义，而这类错误在线上只表现为「限流不管用」。

        命中多规则时取首个超限者（沿用短路顺序），不累加。
        """
        await self._ensure_cache()
        now = time.time()
        bucket = int(now // 60)
        for rule in self._rate_rules:
            # 比 ``.value`` 而非枚举本身：``_RateRule.scope`` 是从库里读回的普通字符串，
            # 显式取值比较不依赖 StrEnum 的 str 子类相等性。
            if rule.scope != scope.value or not self._match_path(rule.path_pattern, path):
                continue
            redis = get_redis()
            key = f"ratelimit:{rule.id}:{client_key}:{bucket}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)
            if count > rule.limit_per_minute:
                # 固定窗口剩余秒数，下限 1：回 0 等于让对端立刻重试，比不回更糟。
                return RateLimitHit(
                    rule_id=rule.id,
                    limit_per_minute=rule.limit_per_minute,
                    retry_after_seconds=max(1, math.ceil(bucket * 60 + 60 - now)),
                )
        return None
```

- [ ] **Step 6: 中间件改用新签名（并导出 `client_ip`）**

在 `backend/packages/miles-core/src/miles_core/web/middlewares/platform_risk.py`：

import 区加 `from miles_core.models.risk import RateLimitScope`。把 `_client_ip` 改名为公开的 `client_ip`（A2A 视图要用它写风控事件的来源 IP）：

```python
def client_ip(request: Request) -> str:
    """请求来源 IP：优先 ``X-Forwarded-For`` 首段（经代理时 ``request.client`` 是代理地址）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
```

`dispatch` 内把 `ip = _client_ip(request)` 改为 `ip = client_ip(request)`，并把限流分支替换为：

```python
        if path.startswith("/api/v1"):
            hit = await platform_risk_enforcer.check_rate_limit(path, ip, scope=RateLimitScope.IP)
            if hit:
                await platform_risk_enforcer.record_event(
                    event_type="rate_limit",
                    severity=RiskSeverity.MEDIUM,
                    ip_address=ip,
                    detail={
                        "kind": "rate_limit",
                        "path": path,
                        "ip": ip,
                        "rule_id": str(hit.rule_id),
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": "请求过于频繁，请稍后再试",
                        "data": None,
                        "trace_id": get_trace_id(),
                    },
                )
```

- [ ] **Step 7: 同步 `conftest` 的替身返回值（否则全部 API 测试变 429）**

`backend/tests/conftest.py` 的 `disable_platform_risk` 里，把

```python
            return_value=(False, None),
```

改为

```python
            # ``check_rate_limit`` 现在回 ``RateLimitHit | None``：回 ``(False, None)`` 这种
            # 非空元组会被判成「命中」，把所有 API 测试变成 429。
            return_value=None,
```

- [ ] **Step 8: 跑测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/admin/test_admin_risk_enforce.py tests/api`
Expected: PASS（`tests/api` 全绿是关键回归信号：中间件 + 替身已同频）

- [ ] **Step 9: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-core/src/miles_core/models/risk.py \
  backend/packages/miles-core/src/miles_core/risk/enforce.py \
  backend/packages/miles-core/src/miles_core/web/middlewares/platform_risk.py \
  backend/alembic/versions/003_adm_rate_limit_rules_scope.py \
  backend/tests/conftest.py backend/tests/admin/test_admin_risk_enforce.py
git commit -F - <<'EOF'
feat(risk): 限流规则增加 scope 维度并回传恢复时间

A2A 对外端点要按调用方的 API Key 计数，而平台通用限流按来源 IP —— 两者共用一个
规则表就必须声明维度，否则「按 Key 限流」只能另起一套配置。默认 ip 保证存量规则
语义不变；check_rate_limit 顺带回传固定窗口剩余秒数，供 429 写 Retry-After。
EOF
```

---

### Task 2: 运营面配置 `scope`（后端 schema + 前端表单）

**Files:**
- Modify: `backend/packages/miles-admin/src/miles_admin/app_ops/schemas/risk.py`
- Modify: `backend/openapi/openapi.snapshot.json`（由 `make openapi-write` 生成）
- Modify: `ui/admin/lib/api.ts`
- Modify: `ui/admin/features/risk/lib/risk-page-shared.ts`
- Modify: `ui/admin/features/risk/hooks/use-risk-page.ts`
- Modify: `ui/admin/features/risk/components/RiskRateLimitSection.tsx`
- Modify: `ui/admin/features/risk/components/RiskRateLimitEditDialog.tsx`
- Test: `backend/tests/admin/test_admin_risk_enforce.py`（追加 DTO 断言）

**Interfaces:**
- Consumes: Task 1 的 `RateLimitScope`（仅用于取值约定，不 import 到 schema 层）。
- Produces: `RateLimitRuleCreate.scope: Literal["ip", "api_key"]`（默认 `"ip"`）、`RateLimitRuleUpdate.scope: Literal["ip", "api_key"] | None`、`RateLimitRuleOut.scope: Literal["ip", "api_key"]`；前端 `RateLimitRule.scope: "ip" | "api_key"`。

- [ ] **Step 1: 写失败测试（DTO 默认值与传递）**

追加到 `backend/tests/admin/test_admin_risk_enforce.py` 末尾：

```python
def test_rate_limit_rule_dto_carries_scope():
    """``scope`` 必须能被创建/更新，且默认 ``ip`` —— 后台建规则时不该被迫选维度。"""
    from miles_admin.app_ops.schemas.risk import RateLimitRuleCreate, RateLimitRuleUpdate

    assert RateLimitRuleCreate(name="r", path_pattern="/api/v1/*").model_dump()["scope"] == "ip"
    assert RateLimitRuleCreate(name="r", path_pattern="/api/v1/*", scope="api_key").model_dump()["scope"] == "api_key"
    # 更新用 exclude_unset：只传 scope 时不得顺手把别的字段写成默认值
    assert RateLimitRuleUpdate(scope="api_key").model_dump(exclude_unset=True) == {"scope": "api_key"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/admin/test_admin_risk_enforce.py -k scope`
Expected: FAIL —— `KeyError: 'scope'`（`model_dump()` 里没有该键）

- [ ] **Step 3: admin schema 加字段**

`backend/packages/miles-admin/src/miles_admin/app_ops/schemas/risk.py`：import 区加 `from typing import Literal`，三处 DTO 各加一行：

`RateLimitRuleCreate`（在 `limit_per_minute` 之后）：

```python
    scope: Literal["ip", "api_key"] = Field("ip", description="计量维度：ip 按来源 IP，api_key 按调用方 API Key")
```

`RateLimitRuleUpdate`（在 `limit_per_minute` 之后）：

```python
    scope: Literal["ip", "api_key"] | None = Field(None, description="计量维度：ip 按来源 IP，api_key 按调用方 API Key")
```

`RateLimitRuleOut`（在 `limit_per_minute` 之后）：

```python
    scope: Literal["ip", "api_key"] = Field(description="计量维度：ip 按来源 IP，api_key 按调用方 API Key")
```

**不要**为此新建枚举类：`Literal` 在 OpenAPI 里落「属性级 inline enum」，而
`tests/models/test_api_enum_parity.py` 的平价守卫只看顶层组件，故不触发「21 个持久化枚举」的
`CASES` / 白名单 / 计数改动。（实测快照：顶层带 `enum` 19 个、属性级 inline 7 个。）

`AdminRiskService` **无需改动**：`create_rate_limit` 走 `body.model_dump()`、
`update_rate_limit` 走 `model_dump(exclude_unset=True)`，`scope` 随之下传，`invalidate_cache()`
也已在两条路径上调用。这条依赖由上面那条 DTO 测试钉住（`model_dump` 里必须真的出现 `scope`）——
若将来有人把 `exclude_unset` 去掉或改成显式字段映射，那条测试会先失败。

- [ ] **Step 4: 重写 OpenAPI 快照并校验**

Run:
```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && make openapi-write && make openapi-check
```
Expected: `OpenAPI snapshot OK`（本步必然改动快照：新增 `scope` 属性）

- [ ] **Step 5: 跑后端测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/admin tests/models`
Expected: PASS（`tests/models` 全绿证明枚举平价与契约守卫未被触发）

- [ ] **Step 6: 前端：类型与表单**

`ui/admin/lib/api.ts` 的 `RateLimitRule` 加一行（在 `limit_per_minute` 之后）：

```ts
  scope: "ip" | "api_key";
```

`ui/admin/features/risk/lib/risk-page-shared.ts` 整体替换为：

```ts
export const RISK_PAGE_DESC = "风险事件、IP 黑名单与 API 限流（私有化部署防护）";

export const RATE_LIMIT_SCOPE_LABELS: Record<string, string> = {
  ip: "按来源 IP",
  api_key: "按 API Key",
};

export const EMPTY_RATE_LIMIT_RULE_FORM = {
  name: "",
  path_pattern: "/api/v1/*",
  limit_per_minute: "60",
  scope: "ip" as "ip" | "api_key",
  description: "",
};

export type RateLimitRuleForm = typeof EMPTY_RATE_LIMIT_RULE_FORM;
```

`ui/admin/features/risk/hooks/use-risk-page.ts` 四处改动：

```ts
      await adminApi.createRateLimit({
        name: ruleForm.name.trim(),
        path_pattern: ruleForm.path_pattern.trim(),
        limit_per_minute: Number(ruleForm.limit_per_minute) || 60,
        scope: ruleForm.scope,
        description: ruleForm.description.trim() || undefined,
      });
```

```ts
    setEditForm({
      name: rule.name,
      path_pattern: rule.path_pattern,
      limit_per_minute: String(rule.limit_per_minute),
      scope: rule.scope,
      description: rule.description ?? "",
    });
```

```ts
      await adminApi.updateRateLimit(editRule.id, {
        name: editForm.name.trim(),
        path_pattern: editForm.path_pattern.trim(),
        limit_per_minute: Number(editForm.limit_per_minute) || 60,
        scope: editForm.scope,
        description: editForm.description.trim() || null,
      });
```

- [ ] **Step 7: 前端：新建区与列表列**

`ui/admin/features/risk/components/RiskRateLimitSection.tsx`：

说明文案改为（原来只说按 IP，现在不准确了）：

```tsx
      <p className="mt-1 text-xs text-ink-muted">
        路径支持通配符（如 <span className="cell-mono">/api/v1/auth/*</span>）。计量维度选「按来源 IP」走平台通用限流；选「按 API Key」用于
        A2A 等按对端计量的场景。
      </p>
```

新建表单里，在「路径模式」之后补一个下拉：

```tsx
          <select className="input-field" value={ruleForm.scope} onChange={(e) => setRuleForm((f) => ({ ...f, scope: e.target.value as "ip" | "api_key" }))}>
            <option value="ip">按来源 IP</option>
            <option value="api_key">按 API Key</option>
          </select>
```

表头「路径」之后补 `<th>维度</th>`；行内「路径」单元格之后补：

```tsx
                    <td className="cell-muted">{RATE_LIMIT_SCOPE_LABELS[r.scope] ?? r.scope}</td>
```

并把空态行的 `colSpan={5}` 改为 `colSpan={6}`。import 区加：

```ts
import { RATE_LIMIT_SCOPE_LABELS } from "@/features/risk/lib/risk-page-shared";
```

- [ ] **Step 8: 前端：编辑对话框**

`ui/admin/features/risk/components/RiskRateLimitEditDialog.tsx` 在「路径模式」输入框之后补：

```tsx
          <select className="input-field" value={editForm.scope} onChange={(e) => setEditForm((f) => ({ ...f, scope: e.target.value as "ip" | "api_key" }))}>
            <option value="ip">按来源 IP</option>
            <option value="api_key">按 API Key</option>
          </select>
```

- [ ] **Step 9: 跑前端质量门**

Run: `cd /Users/xiezhigang/Projects/miles/MilesAI && make check-ui`
Expected: lint 与 prettier 均通过。若 prettier 报格式，先 `cd ui/admin && npm run format` 再复跑。

- [ ] **Step 10: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-admin/src/miles_admin/app_ops/schemas/risk.py \
  backend/openapi/openapi.snapshot.json backend/tests/admin/test_admin_risk_enforce.py \
  ui/admin/lib/api.ts ui/admin/features/risk
git commit -F - <<'EOF'
feat(admin): 限流规则可配置计量维度

规则表有了 scope，后台就得能选 —— 否则「按 API Key 限流」只能靠改库，运营无从配置。
API 侧用 Literal 而非新增枚举类：那是属性级 inline enum，不会惊动 21 个持久化枚举
的平价守卫（CASES / 白名单 / 计数都是冻结的）。
EOF
```

---

### Task 3: 凭证身份传递与 A2A 限流服务层

**Files:**
- Modify: `backend/packages/miles-core/src/miles_core/tenant.py`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/deps_api_auth.py`
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/limits.py`
- Create: `backend/tests/tenant/a2a/test_a2a_rate_limit.py`

**Interfaces:**
- Consumes: Task 1 的 `RateLimitHit`、`RateLimitScope`；`platform_risk_enforcer.check_rate_limit(path, client_key, *, scope)`、`platform_risk_enforcer.record_event(...)`。
- Produces:
  - `TenantContext.api_key_id: UUID | None`（默认 `None`，与既有 `token_jti` 同构）
  - `miles_portal.tenant.a2a.services.limits.check_a2a_rate_limit(ctx, agent_id, *, path: str, ip: str | None) -> RateLimitHit | None`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/tenant/a2a/test_a2a_rate_limit.py`：

```python
"""A2A 按 API Key 限流：维度取值、命中留痕与失败姿态。

服务层单测，不连库不连 Redis —— 风控单例的两条方法在这里被替换。
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from miles_core.risk import enforce as enforce_mod
from miles_core.risk.enforce import RateLimitHit
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.services import limits as limits_mod

AGENT_ID = uuid4()
PATH = f"/api/v1/open/a2a/agents/{AGENT_ID}"


def _ctx(*, with_key: bool = True) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4() if with_key else None,
    )


def test_tenant_context_without_api_key_id_is_still_constructible():
    """既有构造点（JWT 通道）不传该字段也必须能构造 —— 默认 ``None`` 是兼容的关键。"""
    ctx = TenantContext(user_id=uuid4(), tenant_id=uuid4(), username="u", is_superuser=False, permissions=frozenset())
    assert ctx.api_key_id is None


@pytest.mark.asyncio
async def test_hit_is_scoped_by_key_id_and_recorded(monkeypatch):  # noqa: ANN001
    """命中判定按「Key 行 id」分桶，并留一条风控事件。"""
    seen: dict = {}
    events: list[dict] = []
    hit = RateLimitHit(rule_id=uuid4(), limit_per_minute=30, retry_after_seconds=12)
    ctx = _ctx()
    assert ctx.api_key_id is not None

    async def fake_check(path, client_key, *, scope):  # noqa: ANN001
        seen["path"] = path
        seen["client_key"] = client_key
        seen["scope"] = scope
        return hit

    async def fake_record(**kwargs):  # noqa: ANN003
        events.append(kwargs)

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", fake_record)

    got = await limits_mod.check_a2a_rate_limit(ctx, AGENT_ID, path=PATH, ip="1.2.3.4")

    assert got is hit
    assert seen["path"] == PATH
    assert seen["scope"].value == "api_key"
    # 桶键只带 Key 的行 id：Redis 键不该承载凭证材料（明文或哈希都不行）
    assert seen["client_key"] == f"key:{ctx.api_key_id}"
    assert len(events) == 1
    assert events[0]["event_type"] == "a2a_rate_limit"
    assert events[0]["tenant_id"] == ctx.tenant_id
    assert events[0]["ip_address"] == "1.2.3.4"
    assert events[0]["detail"]["apiKeyId"] == str(ctx.api_key_id)


@pytest.mark.asyncio
async def test_no_hit_records_nothing(monkeypatch):  # noqa: ANN001
    events: list[dict] = []

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return None

    async def fake_record(**kwargs):  # noqa: ANN003
        events.append(kwargs)

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", fake_record)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is None
    assert events == []


@pytest.mark.asyncio
async def test_fails_open_when_redis_path_raises(monkeypatch):  # noqa: ANN001
    """Redis 抖动不得让对外端点整体不可用：限流是保护措施，不是正确性依赖。"""

    async def boom(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("redis down")

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", boom)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is None


@pytest.mark.asyncio
async def test_hit_is_still_enforced_when_event_write_fails(monkeypatch):  # noqa: ANN001
    """风控事件写失败不能反向变成放行 —— 命中判定已经成立，放行才是错的方向。"""
    hit = RateLimitHit(rule_id=uuid4(), limit_per_minute=1, retry_after_seconds=5)

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return hit

    async def boom(**_kwargs):  # noqa: ANN003
        raise RuntimeError("db down")

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)
    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "record_event", boom)

    assert await limits_mod.check_a2a_rate_limit(_ctx(), AGENT_ID, path=PATH, ip=None) is hit


@pytest.mark.asyncio
async def test_skips_without_api_key_identity(monkeypatch):  # noqa: ANN001
    """无 Key 身份时不查 Redis（返回 None），且不写事件 —— 不得凭空编造桶键。"""
    called = {"check": 0}

    async def fake_check(*_args, **_kwargs):  # noqa: ANN002, ANN003
        called["check"] += 1
        return None

    monkeypatch.setattr(enforce_mod.platform_risk_enforcer, "check_rate_limit", fake_check)

    assert await limits_mod.check_a2a_rate_limit(_ctx(with_key=False), AGENT_ID, path=PATH, ip=None) is None
    assert called["check"] == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_rate_limit.py`
Expected: FAIL —— `ModuleNotFoundError: No module named 'miles_portal.tenant.a2a.services.limits'`（以及 `TypeError: __init__() got an unexpected keyword argument 'api_key_id'`）

- [ ] **Step 3: `TenantContext` 增加 `api_key_id`**

`backend/packages/miles-core/src/miles_core/tenant.py` 的 `TenantContext` 加字段（放在末尾，前面的字段都已有默认值）：

```python
    api_key_id: UUID | None = None  # X-API-Key 通道的凭证行 id（供按 Key 限流/审计）；JWT 通道为 None
```

- [ ] **Step 4: 鉴权依赖填入该字段**

`backend/packages/miles-portal/src/miles_portal/tenant/agents/deps_api_auth.py` 的 `_ctx_from_api_key` 返回处补 `api_key_id`：

```python
    return TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=row.id,
    )
```

- [ ] **Step 5: 新建 A2A 限流服务**

创建 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/limits.py`：

```python
"""A2A 对外端点的按 API Key 限流（维度的取值约定见 ``RateLimitScope``）。

为什么不在中间件里做：中间件跑在鉴权**之前**，只能从 Header 取 ``X-API-Key`` 当桶键 ——
任意伪造的 Key 都能造出桶键（缓存污染），且拿不到 JSON-RPC ``id``，超限只能回
``id: null``，对端无法把错误对回自己的请求。故检查点放在视图内、鉴权之后。
"""

from __future__ import annotations

from uuid import UUID

from miles_core.logging import get_logger
from miles_core.models.risk import RateLimitScope, RiskSeverity
from miles_core.risk.enforce import RateLimitHit, platform_risk_enforcer
from miles_core.tenant import TenantContext

logger = get_logger(__name__)


def client_bucket_key(ctx: TenantContext) -> str | None:
    """限流桶键：按 API Key 的**行 id**（不用明文/哈希 —— Redis 键不该承载凭证材料）。"""
    return f"key:{ctx.api_key_id}" if ctx.api_key_id else None


async def check_a2a_rate_limit(
    ctx: TenantContext,
    agent_id: UUID,
    *,
    path: str,
    ip: str | None,
) -> RateLimitHit | None:
    """返回命中的限流规则；放行返回 None。

    失败姿态是 **fail-open**：Redis/风控检查出错时放行并记日志。取舍明说 —— 平台对外
    端点因 Redis 抖动而全量 429/5xx，代价大于短时限流失效；限流是保护措施，不是正确性依赖。
    """
    client_key = client_bucket_key(ctx)
    if client_key is None:
        # 非 API Key 通道（JWT 调试）没有对端粒度可依，交回中间件按 IP 兜。
        return None
    try:
        hit = await platform_risk_enforcer.check_rate_limit(path, client_key, scope=RateLimitScope.API_KEY)
    except Exception:
        logger.exception("A2A 限流检查失败，放行本次请求: agent_id=%s", agent_id)
        return None
    if hit is None:
        return None
    # 事件写入单独 try：把两步并进一个 try 的话，写事件失败会被上层 except 吞成「放行」，
    # 而命中判定已经成立 —— 放行才是错的方向。
    try:
        await platform_risk_enforcer.record_event(
            event_type="a2a_rate_limit",
            severity=RiskSeverity.MEDIUM,
            ip_address=ip,
            tenant_id=ctx.tenant_id,
            detail={
                "kind": "a2a_rate_limit",
                "path": path,
                "agent_id": str(agent_id),
                "apiKeyId": str(ctx.api_key_id),
                "rule_id": str(hit.rule_id),
                "limit_per_minute": hit.limit_per_minute,
            },
        )
    except Exception:
        logger.exception("A2A 限流事件写入失败: agent_id=%s", agent_id)
    return hit
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_rate_limit.py tests/models/test_enum_contract.py`
Expected: PASS（带上枚举契约测试，确认新增 `RateLimitScope` 没惊动冻结计数）

- [ ] **Step 7: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-core/src/miles_core/tenant.py \
  backend/packages/miles-portal/src/miles_portal/tenant/agents/deps_api_auth.py \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/limits.py \
  backend/tests/tenant/a2a/test_a2a_rate_limit.py
git commit -F - <<'EOF'
feat(a2a): 按 API Key 限流的服务层与凭证身份传递

限流要按「哪个对端集成」分桶，而 TenantContext 此前只带 auth_via=api_key、不带键的
标识，视图里拿不到可信的桶键。补 api_key_id（与 token_jti 同构）后，检查点得以放在
鉴权之后；失败姿态取 fail-open —— Redis 抖动不该让对外端点整体不可用。
EOF
```

---

### Task 4: 视图接线与 429 响应

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`（`-32000` 常量 + `jsonrpc_error` 支持 `data`）
- Modify: `backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`
- Modify: `backend/tests/api/test_a2a_server_api.py`
- Modify: `backend/tests/tenant/a2a/test_a2a_server_card.py`（纯函数断言）

**Interfaces:**
- Consumes: Task 3 的 `check_a2a_rate_limit`；Task 1 的 `client_ip`。
- Produces: `miles_portal.tenant.a2a.server.RATE_LIMITED = -32000`；`jsonrpc_error(req_id, code, message, data: dict | None = None)`。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的纯函数区：

```python
def test_jsonrpc_error_carries_optional_data():
    """超限要在 ``error.data`` 给结构化细节（规范允许），而既有调用形状必须逐字不变。"""
    assert jsonrpc_error(1, -32602, "坏参数") == {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "坏参数"}}

    with_data = jsonrpc_error(1, server_mod.RATE_LIMITED, "请求过于频繁，请稍后再试", data={"kind": "rate_limit", "retryAfterSeconds": 12})
    assert with_data["error"]["data"] == {"kind": "rate_limit", "retryAfterSeconds": 12}


def test_rate_limited_code_is_in_implementation_defined_range():
    """``-32000`` 属规范保留给实现自定义的服务端错误区间（A2A 已占 -32001..-32007）。"""
    assert server_mod.RATE_LIMITED == -32000
```

追加到 `backend/tests/api/test_a2a_server_api.py`：

```python
@pytest.mark.asyncio
async def test_rpc_endpoint_rate_limited_returns_429_with_jsonrpc_body(as_a2a, api_client, monkeypatch):
    """超限必须让对端能退避：429 + Retry-After，且正文仍是它读得懂的 JSON-RPC 信封。"""
    from miles_core.risk.enforce import RateLimitHit

    async def fake_limit(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=7)

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": "9", "method": "message/send", "params": {}})

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "7"
    body = resp.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == "9"
    assert body["error"]["code"] == -32000
    assert body["error"]["data"]["retryAfterSeconds"] == 7


@pytest.mark.asyncio
async def test_stream_method_rate_limited_before_sse(as_a2a, api_client, monkeypatch):
    """流式请求超限必须在开流前拦下：一旦响应头写成 text/event-stream，429 就塞不进去了。"""
    from miles_core.risk.enforce import RateLimitHit

    async def fake_limit(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=3)

    def fail_stream(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("超限时不应进入 SSE 生成器")

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)
    monkeypatch.setattr(view_mod, "open_a2a_stream", fail_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 429
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_artifact_endpoint_rate_limited_uses_platform_envelope(as_a2a, api_client, monkeypatch):
    """产物下载是普通 HTTP 下载而非 JSON-RPC，超限形状与中间件 429 一致（平台信封）。"""
    from miles_core.risk.enforce import RateLimitHit

    async def fake_limit(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=4)

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)

    resp = await api_client.get(ARTIFACT_PATH.format(AGENT_ID, uuid4(), uuid4()))

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "4"
    assert resp.json()["code"] == 429
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py tests/tenant/a2a/test_a2a_server_card.py -k "rate_limit or jsonrpc_error"`
Expected: FAIL —— `AttributeError: module 'miles_openapi.views.a2a_server' has no attribute 'check_a2a_rate_limit'`

- [ ] **Step 3: 纯逻辑层加常量并扩展信封**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`：在 `TASK_NOT_CANCELABLE = -32002` 之后加

```python
#: 限流拒绝。规范把 -32000..-32099 留给实现自定义（A2A 已占 -32001..-32007），
#: 并要求自定义码「清楚地记录」—— 故写入 docs/guides/a2a.md。
RATE_LIMITED = -32000
```

`jsonrpc_error` 替换为：

```python
def jsonrpc_error(req_id: object, code: int, message: str, data: dict | None = None) -> dict:
    """JSON-RPC 2.0 错误信封；``data`` 非空时附结构化细节（规范允许）。"""
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}
```

- [ ] **Step 4: 视图接线**

`backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`：

import 区加：

```python
from miles_common.trace import get_trace_id
from miles_core.web.middlewares.platform_risk import client_ip
from miles_portal.tenant.a2a.server import (
    PARSE_ERROR,
    RATE_LIMITED,
    agent_card_well_known_path,
    jsonrpc_error,
)
from miles_portal.tenant.a2a.services.limits import check_a2a_rate_limit
```

模块常量区（`_SSE_HEADERS` 之后）加：

```python
#: 超限对端可见文案（与中间件 429 的 message 保持一致）。
_RATE_LIMIT_MESSAGE = "请求过于频繁，请稍后再试"
```

`a2a_jsonrpc` 替换为（新增限流分支；其余逐字不变）：

```python
@router.post("/a2a/agents/{agent_id}")
async def a2a_jsonrpc(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """A2A JSON-RPC 端点（``message/send`` / ``message/stream`` / ``tasks/*``）。

    ``message/stream`` 按 A2A 约定走 SSE，与其它方法共用同一 URL；请求体非 JSON 时回
    -32700 信封。前置校验失败的流式请求回普通 JSON，不进入 SSE。

    限流在鉴权之后、分发之前：维度取 API Key 行 id（见 ``services.limits``）。超限回
    HTTP 429 + ``Retry-After``，正文仍是 JSON-RPC 错误信封（``-32000``）—— 外部客户端
    按 JSON-RPC 解析，且只有它能把错误对回自己的 ``id``。流式请求也在这里被拦下，
    避免响应头已写成 ``text/event-stream`` 后无处安放状态码。
    """
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc_error(None, PARSE_ERROR, "请求体不是合法 JSON"))
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    hit = await check_a2a_rate_limit(ctx, agent_id, path=request.url.path, ip=client_ip(request))
    if hit is not None:
        return JSONResponse(
            jsonrpc_error(
                req_id,
                RATE_LIMITED,
                _RATE_LIMIT_MESSAGE,
                data={"kind": "rate_limit", "retryAfterSeconds": hit.retry_after_seconds},
            ),
            status_code=429,
            headers={"Retry-After": str(hit.retry_after_seconds)},
        )
    base_url = str(request.base_url)
    if isinstance(payload, dict) and payload.get("method") == "message/stream":
        opened = await open_a2a_stream(db, ctx, agent_id, payload)
        if isinstance(opened, dict):
            return JSONResponse(opened)
        return StreamingResponse(opened, media_type="text/event-stream", headers=_SSE_HEADERS)
    return JSONResponse(await handle_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url))
```

`a2a_task_artifact` 替换为（加 `request` 参数与限流分支）：

```python
@router.get("/a2a/agents/{agent_id}/tasks/{task_id}/artifacts/{attachment_id}")
async def a2a_task_artifact(
    agent_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """任务产物下载（``Task.artifacts[].parts[].file.uri`` 指向此处，须带 ``X-API-Key``）。

    平台不暴露对象存储签名 URL；产物只能经由该鉴权端点取回，且限「该智能体该任务」。
    超限走平台信封 429（本路由是普通 HTTP 下载、不是 JSON-RPC，形状与中间件一致）。
    """
    hit = await check_a2a_rate_limit(ctx, agent_id, path=request.url.path, ip=client_ip(request))
    if hit is not None:
        return JSONResponse(
            status_code=429,
            content={"code": 429, "message": _RATE_LIMIT_MESSAGE, "data": None, "trace_id": get_trace_id()},
            headers={"Retry-After": str(hit.retry_after_seconds)},
        )
    data, mime, filename = await read_task_artifact(db, ctx, agent_id, task_id, attachment_id)
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=mime, headers={"Content-Disposition": disposition})
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py tests/tenant/a2a`
Expected: PASS

- [ ] **Step 6: 校验快照无漂移**

Run: `cd /Users/xiezhigang/Projects/miles/MilesAI && make openapi-check`
Expected: `OpenAPI snapshot OK`（本任务只改响应对象、不新增路由与 schema；若报漂移，说明返回类型标注引入了推断，须检查 `-> Response` 是否仍在）

- [ ] **Step 7: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py \
  backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py \
  backend/tests/api/test_a2a_server_api.py backend/tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
feat(a2a): 超限回 429 + Retry-After + JSON-RPC 信封

既有的通用 429 是平台信封，外部 A2A 客户端解析不了、也拿不到自己的 id：它无法退避，
只会持续重试。改用 JSON-RPC 错误码 -32000（规范留给实现自定义的区间）并把恢复秒数
放进 error.data 与 Retry-After；流式请求在开流前拦下，否则状态码无处安放。
EOF
```

---

### Task 5: 审计写入器

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`（action / outcome 常量）
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/audit.py`
- Create: `backend/tests/tenant/a2a/test_a2a_audit.py`

**Interfaces:**
- Consumes: `miles_portal.tenant.audit_log.services.audit_log.write_tenant_audit_log`（签名 `(db, ctx, *, action, resource_type=None, resource_id=None, request=None, detail=None, user_id=None)`，**不 commit**）。
- Produces:
  - 常量：`AUDIT_ACTION_MESSAGE_SEND/STREAM`、`AUDIT_ACTION_TASKS_GET/CANCEL`、`AUDIT_ACTION_ARTIFACT_DOWNLOAD`、`AUDIT_OUTCOME_OK/REJECTED/FAILED/CANCELED`
  - `miles_portal.tenant.a2a.services.audit.write_a2a_audit(*, ctx, agent_id, action, outcome, detail=None) -> None`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/tenant/a2a/test_a2a_audit.py`：

```python
"""A2A 调用审计：独立会话写入、不记正文、失败不惊动业务。"""

from __future__ import annotations

from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.services import audit as audit_mod

AGENT_ID = uuid4()


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4(),
    )


class _FakeSession:
    """记录 ``commit`` / ``closed`` 的最小会话替身。"""

    def __init__(self) -> None:
        self.committed = 0
        self.closed = 0

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        self.closed += 1
        return False

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_audit_uses_own_session_and_commits(monkeypatch):  # noqa: ANN001
    """审计必须自开会话并 commit：复用请求作用域会话时，业务失败回滚会连带吞掉留痕。"""
    session = _FakeSession()
    written: list[dict] = []
    monkeypatch.setattr(audit_mod, "AsyncSessionLocal", lambda: session)

    async def fake_write(_db, ctx, **kwargs):  # noqa: ANN001, ANN003
        written.append({"ctx": ctx, **kwargs})

    monkeypatch.setattr(audit_mod, "write_tenant_audit_log", fake_write)
    ctx = _ctx()

    await audit_mod.write_a2a_audit(ctx=ctx, agent_id=AGENT_ID, action=server_mod.AUDIT_ACTION_MESSAGE_SEND, outcome=server_mod.AUDIT_OUTCOME_OK, detail={"method": "message/send"})

    assert session.closed == 1
    assert session.committed == 1
    assert len(written) == 1
    assert written[0]["action"] == "a2a.message.send"
    assert written[0]["resource_type"] == "agent"
    assert written[0]["resource_id"] == str(AGENT_ID)
    assert written[0]["detail"]["outcome"] == "ok"
    assert written[0]["detail"]["apiKeyId"] == str(ctx.api_key_id)
    assert written[0]["detail"]["method"] == "message/send"


@pytest.mark.asyncio
async def test_audit_failure_never_breaks_caller(monkeypatch):  # noqa: ANN001
    """审计是旁路：写不进去只能记日志，不得让业务调用失败。"""

    def boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(audit_mod, "AsyncSessionLocal", boom)

    await audit_mod.write_a2a_audit(ctx=_ctx(), agent_id=AGENT_ID, action=server_mod.AUDIT_ACTION_TASKS_GET, outcome=server_mod.AUDIT_OUTCOME_OK)


def test_a2a_audit_actions_are_registered_in_audit_meta():
    """写入的 action 必须登记进审计页筛选列表，否则租户在下拉里筛不到自己的 A2A 调用。"""
    from miles_portal.tenant.audit_log.meta import ACTION_FILTER_OPTIONS

    registered = {value for value, _, _ in ACTION_FILTER_OPTIONS}
    expected = {
        server_mod.AUDIT_ACTION_MESSAGE_SEND,
        server_mod.AUDIT_ACTION_MESSAGE_STREAM,
        server_mod.AUDIT_ACTION_TASKS_GET,
        server_mod.AUDIT_ACTION_TASKS_CANCEL,
        server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD,
    }
    assert expected <= registered, f"未登记：{sorted(expected - registered)}"


def test_audit_actions_are_namespaced():
    """动作名统一 ``a2a.`` 前缀：租户审计页按动作筛选时才聚得起来。"""
    assert all(
        action.startswith("a2a.")
        for action in (
            server_mod.AUDIT_ACTION_MESSAGE_SEND,
            server_mod.AUDIT_ACTION_MESSAGE_STREAM,
            server_mod.AUDIT_ACTION_TASKS_GET,
            server_mod.AUDIT_ACTION_TASKS_CANCEL,
            server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        )
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_audit.py`
Expected: FAIL —— `ModuleNotFoundError: No module named 'miles_portal.tenant.a2a.services.audit'`

- [ ] **Step 3: 纯逻辑层加动作/结果常量**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`，在 `RATE_LIMITED` 之后加：

```python
#: 租户审计 ``action``（落 ``aud_logs``）。只记「谁在何时以何结果调了什么」——
#: ``aud_logs`` 是租户可见面，不写消息正文（正文可能含隐私内容）。
AUDIT_ACTION_MESSAGE_SEND = "a2a.message.send"
AUDIT_ACTION_MESSAGE_STREAM = "a2a.message.stream"
AUDIT_ACTION_TASKS_GET = "a2a.tasks.get"
AUDIT_ACTION_TASKS_CANCEL = "a2a.tasks.cancel"
AUDIT_ACTION_ARTIFACT_DOWNLOAD = "a2a.artifact.download"

#: 审计 ``detail.outcome`` 取值。
AUDIT_OUTCOME_OK = "ok"
AUDIT_OUTCOME_REJECTED = "rejected"
AUDIT_OUTCOME_FAILED = "failed"
AUDIT_OUTCOME_CANCELED = "canceled"
```

- [ ] **Step 4: 新建审计写入器**

创建 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/audit.py`：

```python
"""A2A 调用审计（落租户流水 ``aud_logs``）。

为什么自开会话：``write_tenant_audit_log`` 的契约是「不 commit，由调用方会话收尾」。
若复用请求作用域的 ``db``，``message/send`` 业务失败回滚会**连带丢掉留痕** —— 而失败
恰恰是最需要留痕的时候。流式请求更甚：请求作用域会话在开流时就已经提交释放了
（见 message-stream 设计的 §3.5），根本没有会话可复用。
"""

from __future__ import annotations

from uuid import UUID

from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.tenant import TenantContext
from miles_portal.tenant.audit_log.services.audit_log import write_tenant_audit_log

logger = get_logger(__name__)


async def write_a2a_audit(
    *,
    ctx: TenantContext,
    agent_id: UUID,
    action: str,
    outcome: str,
    detail: dict | None = None,
) -> None:
    """写一条 A2A 调用流水；失败只记日志，绝不影响业务返回（审计是旁路）。"""
    payload: dict = {"outcome": outcome, "apiKeyId": str(ctx.api_key_id) if ctx.api_key_id else None}
    if detail:
        payload.update(detail)
    try:
        async with AsyncSessionLocal() as db:
            await write_tenant_audit_log(
                db,
                ctx,
                action=action,
                resource_type="agent",
                resource_id=str(agent_id),
                detail=payload,
            )
            await db.commit()
    except Exception:
        logger.exception("A2A 审计写入失败: action=%s agent_id=%s", action, agent_id)
```

- [ ] **Step 5: 登记审计筛选动作**

`backend/packages/miles-portal/src/miles_portal/tenant/audit_log/meta.py` 的 `ACTION_FILTER_OPTIONS`，在 `("compliance.scan", ...)` 之后插入（顺序按域分组，`a2a` 紧邻 `agent.*`）：

```python
    ("a2a.message.send", "A2A 调用智能体", None),
    ("a2a.message.stream", "A2A 流式调用智能体", None),
    ("a2a.tasks.get", "A2A 查询任务", None),
    ("a2a.tasks.cancel", "A2A 取消任务", None),
    ("a2a.artifact.download", "A2A 下载任务产物", None),
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_audit.py tests/api/test_domain_meta.py`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/audit.py \
  backend/packages/miles-portal/src/miles_portal/tenant/audit_log/meta.py \
  backend/tests/tenant/a2a/test_a2a_audit.py
git commit -F - <<'EOF'
feat(a2a): 调用审计写入器与筛选动作登记

A2A 调用此前没有任何留痕，租户看到「我的智能体被外部调了多少次、谁调的」无从查起。
审计自开会话并自行 commit：复用请求作用域会话时，业务失败回滚会连带吞掉留痕，而
失败恰恰最需要留痕。只记谁在何时以何结果调了什么，不写消息正文（租户可见面）。
EOF
```

---

### Task 6: 审计接入三个调用点

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`
- Modify: `backend/tests/tenant/a2a/test_a2a_server_card.py`

**Interfaces:**
- Consumes: Task 5 的 `write_a2a_audit` 与全部常量。
- Produces: `handle_a2a_rpc` 拆出私有 `_dispatch_a2a_rpc`（签名与原 `handle_a2a_rpc` 一致）；`miles_portal.tenant.a2a.services.server._STREAM_OUTCOME_BY_STATE`。

- [ ] **Step 1: 写失败测试（含测试替身 fixture）**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的 import 区补 `from miles_portal.tenant.a2a.services import audit as audit_svc`，并在 `--- 2. 服务：发布门槛` 小节开头加一个 autouse fixture（**必须 autouse**：该文件里所有调用都会走审计，不替换就会去连真库）：

```python
@pytest.fixture(autouse=True)
def a2a_audit_recorder(monkeypatch):  # noqa: ANN001
    """审计走独立会话；单测不连库，故默认替换为记录器，专测再从返回值断言。

    与本文件既有的 ``_patch_session`` 不冲突：那条替换的是 ``server_svc.AsyncSessionLocal``
    （轮次会话），审计用的是 ``services.audit`` 里的同名对象。
    """
    recorded: list[dict] = []

    async def fake_write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    monkeypatch.setattr(server_svc, "write_a2a_audit", fake_write)
    return recorded
```

再追加测试：

```python
@pytest.mark.asyncio
async def test_handle_rpc_audits_message_send(a2a_audit_recorder):  # noqa: ANN001
    """一次调用一条流水，outcome 由最终信封决定：审计不该散在各 _handle_* 里重复判定。"""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": {"contextId": "ctx-1", "parts": [{"kind": "text", "text": "你好"}]}}}

    await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert [r["action"] for r in a2a_audit_recorder] == [server_mod.AUDIT_ACTION_MESSAGE_SEND]
    record = a2a_audit_recorder[0]
    assert record["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert record["agent_id"] == AGENT_ID
    assert record["detail"]["method"] == "message/send"
    assert record["detail"]["contextId"] == "ctx-1"


@pytest.mark.asyncio
async def test_handle_rpc_audits_failure_with_error_code(a2a_audit_recorder):  # noqa: ANN001
    """失败也要留痕，并带上错误码：失败恰恰是最需要留痕的时候。"""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {}}

    await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert a2a_audit_recorder[0]["action"] == server_mod.AUDIT_ACTION_TASKS_GET
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_handle_rpc_does_not_audit_unsupported_method(a2a_audit_recorder):  # noqa: ANN001
    """不支持的方法没有对应动作名，不编造流水。"""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {}}

    await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert a2a_audit_recorder == []


@pytest.mark.asyncio
async def test_stream_final_frame_audits_completed(a2a_audit_recorder, monkeypatch):  # noqa: ANN001
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        return ChatResponse(answer="好了")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())
    await _collect(stream)

    assert [r["action"] for r in a2a_audit_recorder] == [server_mod.AUDIT_ACTION_MESSAGE_STREAM]
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert a2a_audit_recorder[0]["detail"]["method"] == "message/stream"
    assert isinstance(a2a_audit_recorder[0]["detail"]["durationMs"], int)


@pytest.mark.asyncio
async def test_stream_disconnect_audits_canceled(a2a_audit_recorder, monkeypatch):  # noqa: ANN001
    """对端断连是最需要留痕的一种「调用」：没有终态帧，但必须有一条 canceled 流水。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await on_delta("半")
        await asyncio.sleep(5)
        return ChatResponse(answer="不该到这里")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    assert await anext(stream)  # 首帧 Task
    assert await anext(stream)  # 增量帧
    await stream.aclose()

    assert [r["outcome"] for r in a2a_audit_recorder] == [server_mod.AUDIT_OUTCOME_CANCELED]
    assert a2a_audit_recorder[0]["action"] == server_mod.AUDIT_ACTION_MESSAGE_STREAM


@pytest.mark.asyncio
async def test_task_artifact_read_audits_download(a2a_audit_recorder, monkeypatch):  # noqa: ANN001
    """产物下载也要留痕：否则「谁把产物取走了」查不到。"""
    attachment_id = uuid4()
    job = _artifact_job(agent_id=AGENT_ID, attachments=(str(attachment_id),))

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _FakeAttachments:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def read_attachment_bytes(self, _attachment_id):  # noqa: ANN001
            return b"DATA", "image/png", "a.png"

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "AttachmentService", _FakeAttachments)

    data, _mime, _name = await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)

    assert data == b"DATA"
    assert [r["action"] for r in a2a_audit_recorder] == [server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD]
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert a2a_audit_recorder[0]["detail"]["taskId"] == str(job.id)


@pytest.mark.asyncio
async def test_task_artifact_failure_is_audited(a2a_audit_recorder, monkeypatch):  # noqa: ANN001
    """取不到也要留痕：越权尝试（404）本身就是排查线索，不能只在成功时记。"""
    job = _artifact_job(agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)

    with pytest.raises(NotFoundError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, uuid4())

    assert [r["action"] for r in a2a_audit_recorder] == [server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD]
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND
```

**测试放置位置**：以上用例统一追加在文件**末尾**（第 6 节 `message/stream` 之后）——`_job` / `_artifact_job` / `_agent` / `_Db` / `_stream_params` / `_collect` / `_patch_session` 都是模块级助手，从文件任何位置都可用。无需新增 import。

另外在既有 `test_open_stream_maps_compliance_block_to_rejected` 的**末尾**补一行断言，覆盖「拦截」这一种 outcome：

```python
    assert [r["outcome"] for r in a2a_audit_recorder] == [server_mod.AUDIT_OUTCOME_REJECTED]
```

并把该用例的签名加上 fixture 参数（`async def test_open_stream_maps_compliance_block_to_rejected(a2a_audit_recorder, monkeypatch):`；若原本已是 `(monkeypatch)`，只需把 fixture 插到前面）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py -k audit`
Expected: FAIL —— `AttributeError: module 'miles_portal.tenant.a2a.services.server' has no attribute 'write_a2a_audit'`

- [ ] **Step 3: 调用点①——`handle_a2a_rpc` 拆出分发并统一留痕**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`：

import 区加 `import time`。在 `from miles_portal.tenant.a2a.server import (...)` 的既有项中按字母序插入以下新名字（**不要删改任何既有项**）：`AUDIT_ACTION_MESSAGE_SEND`、`AUDIT_ACTION_MESSAGE_STREAM`、`AUDIT_ACTION_ARTIFACT_DOWNLOAD`、`AUDIT_OUTCOME_CANCELED`、`AUDIT_OUTCOME_FAILED`、`AUDIT_OUTCOME_OK`、`AUDIT_OUTCOME_REJECTED`（`TASK_STATE_*` 与 `build_a2a_status_update` 已在块内）。再在该 import 块之后加一行：

```python
from miles_portal.tenant.a2a.services.audit import write_a2a_audit
```

模块级加（放在 `_TERMINAL_JOB_STATUSES` 一类常量附近）：

```python
#: JSON-RPC 方法 → 租户审计 ``action``。``message/stream`` 不在此表：它的 outcome 只有
#: 终态帧才知道，由 ``_stream_turn`` 自己写。不支持的方法没有对应动作名，不编造流水。
_AUDIT_ACTION_BY_METHOD = {
    "message/send": AUDIT_ACTION_MESSAGE_SEND,
    "tasks/get": AUDIT_ACTION_TASKS_GET,
    "tasks/cancel": AUDIT_ACTION_TASKS_CANCEL,
}

#: 流式终态 → 审计 ``outcome``。``working`` 是「本流结束但任务还在跑」（对端转
#: ``tasks/get`` 轮询），对审计而言属正常完成。
_STREAM_OUTCOME_BY_STATE = {
    TASK_STATE_COMPLETED: AUDIT_OUTCOME_OK,
    TASK_STATE_WORKING: AUDIT_OUTCOME_OK,
    TASK_STATE_FAILED: AUDIT_OUTCOME_FAILED,
    TASK_STATE_REJECTED: AUDIT_OUTCOME_REJECTED,
}


def _elapsed_ms(started: float) -> int:
    """自 ``started``（``time.monotonic()``）起的毫秒数。"""
    return int((time.monotonic() - started) * 1000)
```

`TASK_STATE_REJECTED` 与 `AUDIT_OUTCOME_REJECTED` 都要在 import 清单里。

把现有 `handle_a2a_rpc` 整体改名为 `_dispatch_a2a_rpc`（函数体逐字不动），并在其**之前**新增对外的 `handle_a2a_rpc`：

```python
async def handle_a2a_rpc(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
    *,
    base_url: str,
) -> dict:
    """JSON-RPC 2.0 分发入口：分发并统一留租户审计。

    审计放在这一层而非各 ``_handle_*`` 内：一次调用只该有一条流水，且 ``outcome`` 由最终
    信封决定（有 ``error`` 即失败），不必在各处重复判定。
    """
    started = time.monotonic()
    envelope = await _dispatch_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    method = payload.get("method") if isinstance(payload, dict) else None
    action = _AUDIT_ACTION_BY_METHOD.get(method) if isinstance(method, str) else None
    if action is not None:
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=action,
            outcome=_rpc_audit_outcome(envelope),
            detail=_rpc_audit_detail(payload, envelope, started=started, method=method),
        )
    return envelope


def _rpc_audit_outcome(envelope: object) -> str:
    """按最终信封判定结果：有 ``error`` 即失败（协议级错误也不例外）。"""
    return AUDIT_OUTCOME_FAILED if isinstance(envelope, dict) and "error" in envelope else AUDIT_OUTCOME_OK


def _rpc_audit_detail(payload: object, envelope: object, *, started: float, method: str) -> dict:
    """审计细节：方法、耗时，以及能低成本取到的任务/会话标识与错误码。"""
    detail: dict = {"method": method, "durationMs": _elapsed_ms(started)}
    params = payload.get("params") if isinstance(payload, dict) else None
    if isinstance(params, dict):
        if isinstance(params.get("id"), str):
            detail["taskId"] = params["id"]
        message = params.get("message")
        if isinstance(message, dict) and isinstance(message.get("contextId"), str):
            detail["contextId"] = message["contextId"]
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if isinstance(error, dict):
        detail["errorCode"] = error.get("code")
    return detail
```

- [ ] **Step 4: 调用点②——流式终态与断连留痕**

在 `_stream_turn` 开头（`task_id = str(uuid4())` 之前）加：

```python
    started = time.monotonic()
```

在 `on_delta` 定义之前加终态辅助（把四处终态帧构造收敛到一处，顺带只写一次审计）：

```python
    async def terminal_frame(state: str, text: str, *, job_task_id: str | None = None) -> str:
        """终态帧 + 审计：``message/stream`` 的 outcome 只有走到终态才知道。"""
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=AUDIT_ACTION_MESSAGE_STREAM,
            outcome=_STREAM_OUTCOME_BY_STATE[state],
            detail={"method": "message/stream", "contextId": context_id, "taskId": task_id, "durationMs": _elapsed_ms(started)},
        )
        return _sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=state,
                    timestamp=_now(),
                    text=text,
                    final=True,
                    job_task_id=job_task_id,
                ),
            )
        )
```

（`AUDIT_ACTION_MESSAGE_STREAM` 补进 import 清单；`build_a2a_status_update` 的 `job_task_id` 是既有参数。）

四处终态构造替换为：

```python
    if error is not None:
        state = TASK_STATE_REJECTED if isinstance(error, BadRequestError) else TASK_STATE_FAILED
        yield await terminal_frame(state, _failure_text(error))
        return
    if response is None:
        # 兜底：error 与 response 同时为空，只可能来自「任务在记录 outcome 之前就没了」。
        # 回一帧 failed 终态，别让对端等到「流自然结束却没有终态帧」而只能超时。
        yield await terminal_frame(TASK_STATE_FAILED, "智能体执行失败")
        return
    job = _first_active_job(response.generative_jobs)
    if job:
        # 产物未就绪：以 working + final 收尾（final 只表示本流结束），并给出真实
        # job id —— 对端据此转向 tasks/get 轮询状态与产物。
        yield await terminal_frame(TASK_STATE_WORKING, response.answer, job_task_id=str(job["id"]))
        return
    yield await terminal_frame(TASK_STATE_COMPLETED, response.answer)
```

消费循环的 `try/finally` 增加 `except GeneratorExit`（在 `finally` **之前**）：

```python
    try:
        yield _sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=TASK_STATE_WORKING,
                    timestamp=_now(),
                ),
            )
        )
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_SECONDS)
            except TimeoutError:
                # 保活：注释帧不进入 JSON 序列，对端解析器忽略它，只用于维持连接。
                yield SSE_HEARTBEAT_FRAME
                continue
            if item is _STREAM_DONE:
                break
            yield _sse_frame(
                jsonrpc_result(
                    req_id,
                    build_a2a_status_update(
                        task_id=task_id,
                        context_id=context_id,
                        state=TASK_STATE_WORKING,
                        timestamp=_now(),
                        text=item,
                        final=False,
                    ),
                )
            )
    except GeneratorExit:
        # 对端断连：``aclose()`` 抛出 GeneratorExit，后面的终态帧不会再发，但留痕要在这里
        # 补上 —— 「谁中途掐了连接」正是审计要回答的问题之一。此处只能 await、不能再 yield。
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=AUDIT_ACTION_MESSAGE_STREAM,
            outcome=AUDIT_OUTCOME_CANCELED,
            detail={"method": "message/stream", "contextId": context_id, "taskId": task_id, "durationMs": _elapsed_ms(started)},
        )
        raise
    finally:
        # 消费端提前退出（客户端断连）：必须取消对话任务，否则 LLM 调用会跑到底白烧 token。
        # 先置 stopped 再取消：让 run_turn 的 finally 不再往无人消费的队列里塞哨兵。
        stopped = True
        if not turn.done():
            turn.cancel()
```

（`AUDIT_OUTCOME_CANCELED` 补进 import 清单。）

- [ ] **Step 5: 调用点③——产物下载留痕**

`read_task_artifact` 替换为：

```python
async def read_task_artifact(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
) -> tuple[bytes, str, str]:
    """下载某任务产物，返回 ``(data, mime_type, filename)``。

    授权精确到「该智能体 · 该任务 · 该产物」：先验任务归属，再验附件确为该任务产物，
    否则本租户任意附件都能被取走。成败都留一条审计流水（「谁把产物取走了」要查得到）。
    """
    started = time.monotonic()
    try:
        job = await _load_owned_agent_task(db, ctx, agent_id, task_id)
        if str(attachment_id) not in artifact_ids_from_job_result(job.result):
            raise NotFoundError("附件不是该任务的产物")
        data, mime, filename = await AttachmentService(db, ctx).read_attachment_bytes(attachment_id)
    except NotFoundError:
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
            outcome=AUDIT_OUTCOME_FAILED,
            detail={"taskId": str(task_id), "errorCode": TASK_NOT_FOUND, "durationMs": _elapsed_ms(started)},
        )
        raise
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_OK,
        detail={"taskId": str(task_id), "durationMs": _elapsed_ms(started)},
    )
    return data, mime, filename
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && uv run python -m pytest -q tests/tenant/a2a tests/api/test_a2a_server_api.py`
Expected: PASS。**重点核对既有断言未变**：`test_open_stream_emits_task_then_increments_then_final` 的 `session.closed == 1` / `db.committed == 1` 必须仍然成立（autouse fixture 已把审计替换掉，不会再开第二个会话）。

- [ ] **Step 7: 全量后端测试**

Run: `cd /Users/xiezhigang/Projects/miles/MilesAI && make test-backend`
Expected: 全绿（前序批次基线 1351 passed，本批新增用例后更多）

- [ ] **Step 8: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py \
  backend/tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
feat(a2a): 三个调用点接入审计

审计落点：JSON-RPC 分发统一写一条（outcome 由最终信封决定）、流式在终态帧与断连时
各写一条、产物下载成败各写一条。流式的断连分支必须单独处理 —— GeneratorExit 之后
终态帧不会再发，而「谁中途掐了连接」正是审计要回答的问题。终态帧构造顺带收敛到一处，
避免四处重复。
EOF
```

---

### Task 7: 文档同步与全量质量门

**Files:**
- Modify: `docs/guides/a2a.md`
- Modify: `docs/features/a2a-interconnect.md`
- Modify: `backend/README.md`

- [ ] **Step 1: 在对接指南补限流与审计两节**

`docs/guides/a2a.md`：在「待做」小节**之前**插入：

```markdown
## 限流

调用端点按 **API Key** 限流（维度 = 单个对端集成；轮换 Key 即换桶）。阈值来自运营后台
「风控 → 限流配置」里 `scope = api_key` 的规则，路径模式按端点路径匹配（如
`/api/v1/open/a2a/*`）。

超限返回 **HTTP 429**：

```
Retry-After: 12
```

```json
{"jsonrpc": "2.0", "id": "9", "error": {"code": -32000, "message": "请求过于频繁，请稍后再试", "data": {"kind": "rate_limit", "retryAfterSeconds": 12}}}
```

- `-32000` 落在 A2A 规范留给实现自定义的服务端错误区间（`-32000..-32099`）。
- 产物下载端点同为 429 + `Retry-After`，但正文是平台信封 `{code,message,data}`（它是普通
  HTTP 下载、不是 JSON-RPC）。
- `message/stream` 的超限在**开流之前**判出，故回普通 JSON 而非 SSE 帧 —— 对端按状态码
  处理即可，不必解析半条流。
- 命中会记一条平台风控事件（`a2a_rate_limit`，含 `apiKeyId`）。

## 审计

每次调用在租户审计流水（`aud_logs`）留一条，可在工作台「系统 → 审计日志」按动作筛选：

| 动作 | 触发 |
|---|---|
| `a2a.message.send` | `message/send` |
| `a2a.message.stream` | `message/stream`（终态或对端断连时记一次） |
| `a2a.tasks.get` | `tasks/get` |
| `a2a.tasks.cancel` | `tasks/cancel` |
| `a2a.artifact.download` | 产物下载 |

记录内容为「谁（`apiKeyId`）在何时以何结果（`outcome`：`ok` / `rejected` / `failed` /
`canceled`）调用了哪个智能体的哪个方法」，**不含消息正文**。被限流拒绝的请求只记风控事件、
不记审计流水。
```

- [ ] **Step 2: 同步特性文档**

`docs/features/a2a-interconnect.md` 的小节 5 之后追加一条：

```markdown
6. 对外调用：按 API Key 限流（429 + `Retry-After` + JSON-RPC `-32000`）；每次调用落租户审计
   `a2a.*`，超限另落风控事件 `a2a_rate_limit`
```

- [ ] **Step 3: 修正 README 的过期描述**

`backend/README.md` 第 233 行的「中间件落地」行把「IP 黑名单、限流等待补充」改为现状（两者都已落地，且限流现在分 `ip` / `api_key` 两个维度）：

```markdown
| 中间件落地 | trace / access_log / platform_risk（IP 黑名单 + 按 `scope` 维度的限流）已在 `middlewares/` |
```

- [ ] **Step 4: 跑全量质量门**

Run: `cd /Users/xiezhigang/Projects/miles/MilesAI && make check && make check-ui`
Expected: lint / format / layers（`7 kept, 0 broken`）/ OpenAPI 快照 / 后端全量测试全绿；前端 lint 与 prettier 通过。

- [ ] **Step 5: 确认迁移可用（需本地 PG，可选但建议）**

Run:
```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && make migrate && make verify-db
```
Expected: 迁移到 head（`003`）后校验通过。无本地 PG 时跳过本步——列形状已由 Task 1 的模型断言覆盖，本步只验 ALTER 语句在真实 PG 上可执行。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add docs/guides/a2a.md docs/features/a2a-interconnect.md backend/README.md
git commit -F - <<'EOF'
docs(a2a): 补限流与审计的对接语义

对端需要知道超限会看到什么：自定义错误码 -32000 按规范要求必须记录在案，429 与
Retry-After 是它唯一的退避信号。审计一节说明记录范围与不记正文的取舍。
EOF
```

---

## 交付检查表

- [ ] `scope` 维度可用，存量规则（默认 `ip`）行为不变
- [ ] A2A 调用按 API Key 分桶限流，超限 429 + `Retry-After` + JSON-RPC `-32000`
- [ ] `message/stream` 超限不进 SSE；产物下载超限走平台信封
- [ ] 五种 `a2a.*` 动作落 `aud_logs`（含流式断连的 `canceled`），不记消息正文
- [ ] 审计/限流失败不影响业务返回；Redis 异常 fail-open 且记日志
- [ ] 运营后台可配置 `scope`；`a2a.*` 动作在审计页筛选下拉里可选
- [ ] `make check` + `make check-ui` 全绿；OpenAPI 快照已随 `scope` 更新并提交
