# A2A 专用限流与审计（设计）

- 日期：2026-09-20
- 范围：A2A 对外 Server 面的「按 API Key 限流」与「A2A 调用审计」
- 关联：`docs/guides/a2a.md`、`docs/features/a2a-interconnect.md`

## 1. 背景与问题

A2A 对外端点（Card、JSON-RPC、产物下载）目前只复用平台通用设施，两个缺口：

**1.1 限流维度不适用。** `PlatformRiskMiddleware`（`miles_core/web/middlewares/platform_risk.py`）对
`/api/v1` 按 **IP** 限流：规则取自 `adm_rate_limit_rules`，命中写 `RiskEvent` 并返回 429。两个问题：

- 维度是 IP 而不是「某个对端集成」。同一个对端可能多出口 IP（限不住），不同对端可能共出口（互相
  连坐）；而 A2A 的多对端接入（各自一把 Key）恰恰需要「一把 Key 一个桶」。
- 429 的响应体是平台信封 `{code,message,data}`。外部 A2A 客户端按 JSON-RPC 解析，会拿到一个它读不懂
  的体；且它拿不到 JSON-RPC `id`，无法把错误对回自己的请求。

**1.2 审计缺失。** A2A 调用没有落任何审计。租户看到「我的智能体被外部调用了多少次、谁调的」，运维
看到「谁在刷」，都无从查起。规范 §11 也把 rate limiting / resource limits 列为合规要求
（v0.3 规范：*"Implement rate limiting, concurrency controls, and resource limits to protect agents
from abuse or overload"*），但**未**规定超限响应的状态码与错误码形状，故形状由本平台决定并记录。

**1.3 维度只能在鉴权之后拿到。** `require_agent_api_key`（`miles_portal/tenant/agents/deps_api_auth.py`）
在入口就解析出 `AgentApiKey` 行，但该身份**没有**往外传：`TenantContext` 只有 `auth_via="api_key"`，
没有键的标识。限流要用它做桶键，就得先把这一处补上。

## 2. 决策

| # | 决策 | 选定 |
|---|---|---|
| 1 | 限流计量维度 | **按 API Key**（= 单个对端集成）；轮换 Key 即换桶 |
| 2 | 阈值配置来源 | **扩展现有 `adm_rate_limit_rules`**（加 `scope`），复用运营后台界面 |
| 3 | 超限响应形状 | **HTTP 429 + `Retry-After` + JSON-RPC 错误信封**（`-32000`，`data.retryAfterSeconds`） |
| 4 | 审计落点 | **分两路**：每次调用落租户审计 `aud_logs`；超限另落 `RiskEvent` |

## 3. 设计

### 3.1 规则表加 `scope`

`RateLimitRule`（`miles_core/models/risk.py`）新增：

```python
class RateLimitScope(enum.StrEnum):
    """限流计量维度。"""
    IP = "ip"
    API_KEY = "api_key"
```

- 列类型 `String(16)`，`nullable=False`，`default` / `server_default` 均为 `'ip'`。
  **默认 `ip` 是向后兼容的关键**：存量规则语义不变（仍由中间件按 IP 执行），无需数据回填。
- 不引入 PG 原生枚举：`RiskSeverity` 用 `SAEnum` 是因为它已存在，新增枚举类型要 `CREATE TYPE`
  且拖累 `downgrade`，而本字段只有两个取值、且校验在应用层。
- 匹配语义：`path_pattern` 命中 path **且** `scope == 本次维度`。两个维度各自独立计数。
- `_RateRule`（`enforce.py` 内的缓存 DTO）加 `scope` 字段，`_ensure_cache` 一并加载。

### 3.2 `check_rate_limit` 签名与返回值

现状：`check_rate_limit(path, client_key) -> tuple[bool, UUID | None]`，只回「是否超限」与规则 ID ——
`Retry-After` 需要剩余秒数，故改为返回结果对象：

```python
@dataclass(frozen=True)
class RateLimitHit:
    """命中的限流规则与恢复时间。"""
    rule_id: UUID
    limit_per_minute: int
    retry_after_seconds: int


async def check_rate_limit(self, path: str, client_key: str, *, scope: str) -> RateLimitHit | None: ...
```

- `scope` 为**必填关键字**：中间件与 A2A 两条调用路径都必须显式声明自己是哪个维度，避免将来新增调用
  方时默默继承一个错的语义。
- `retry_after_seconds = max(1, ceil(bucket_start + 60 - now))`：固定窗口（沿用现有 `bucket = int(time
  // 60)` 与 `ratelimit:{rule.id}:{client_key}:{bucket}` 键式，不改），至少 1 秒。
- 中间件调用点改为 `check_rate_limit(path, ip, scope=RateLimitScope.IP)`，行为与现状等价。
- 多规则同时命中时取**首个超限**者（沿用现有短路顺序），文档明说。

### 3.3 凭证身份传递

`TenantContext`（`miles_core/tenant.py`）加 `api_key_id: UUID | None = None`，与既有 `token_jti` 同构
（先例：`token_jti` 就是给同一类用途——把凭证身份带出鉴权 dep）。`_ctx_from_api_key` 里填 `row.id`。

只加 id、**不加 `key_prefix`**：`key_prefix` 是给人看的展示值，但把凭证派生值铺到一个被广泛传递的
上下文对象上没有收益 —— 审计里记 `apiKeyId`，需要前缀时查一次 `agt_agent_api_keys` 即可。

### 3.4 桶键

`client_key = f"key:{ctx.api_key_id}"` —— 用**行 id 而非 Key 明文或哈希**：Redis 键不该承载凭证材料，
且行 id 已唯一标识「哪个对端集成的哪把 Key」。

### 3.5 检查点与超限响应

检查点两处，都在**鉴权之后**（维度可信）：

| 端点 | 检查位置 | 超限响应 |
|---|---|---|
| `POST /api/v1/open/a2a/agents/{id}`（JSON-RPC） | 视图解析 body 之后、分发之前 | 429 + `Retry-After` + **JSON-RPC 信封**（`code=-32000`，`message="请求过于频繁，请稍后再试"`，`data={"kind":"rate_limit","retryAfterSeconds":N}`） |
| `GET .../tasks/{tid}/artifacts/{aid}` | 视图取产物之前 | 429 + `Retry-After` + **平台信封** `{code,message,data}` |

拆分两种形状的理由：GET 产物下载是普通 HTTP 下载（不是 JSON-RPC），对端按状态码处理，与既有中间件的
429 形状保持一致；而 `message/stream` 的超限必须在**开流之前**拦下，回普通 JSON（不进 SSE）。

所需改动：

- `jsonrpc_error`（`miles_portal/tenant/a2a/server.py`）加可选 `data: dict | None = None`，仅当非 `None`
  时写入 `error.data` —— 保持既有调用与断言的字典形状不变。
- 新常量 `RATE_LIMITED = -32000`（spec §8.2 的 `-32000..-32099` 是实现自定义区间；A2A 已占
  `-32001..-32007`，`-32000` 空着）。规范要求自定义码「清楚地记录」，故写入 `docs/guides/a2a.md`。
- 超限同时写 `RiskEvent`：`event_type="a2a_rate_limit"`、`severity=MEDIUM`、`tenant_id`、
  `ip_address`、`detail` 含 `path` / `rule_id` / `agent_id` / `apiKeyId`。
- `_client_ip` 由私有改为公开 `client_ip(request)`（`platform_risk.py`），中间件与 A2A 共用。这是本批
  触及代码内的定向改进，不顺手合并 `auth.py` / `access_log.py` 里另两份同逻辑副本。

### 3.6 审计

每次 A2A 调用落 `aud_logs`（`TenantAuditLog`，经 `write_tenant_audit_log`），`resource_type="agent"`、
`resource_id=agent_id`：

| action | 触发 |
|---|---|
| `a2a.message.send` | `message/send` |
| `a2a.message.stream` | `message/stream`（流收尾时记一次） |
| `a2a.tasks.get` | `tasks/get` |
| `a2a.tasks.cancel` | `tasks/cancel` |
| `a2a.artifact.download` | 产物下载 |

`detail` 字段：`method` / `contextId` / `taskId` / `apiKeyId` / `durationMs` / `outcome`
（`ok` \| `rejected` \| `failed` \| `canceled`）/ `errorCode`。

三条硬约束：

1. **不记录消息正文。** `aud_logs` 是租户可见面，正文可能含隐私内容；审计只记「谁在何时以何结果调了
   什么」。
2. **一律独立会话**（`AsyncSessionLocal` + 自行 commit）。若复用请求作用域会话：`message/send` 业务失败
   回滚会**连带丢掉留痕**，而失败恰恰是最需要留痕的时候。
3. **审计写失败绝不影响业务返回**（`try/except` + 日志）。审计是旁路。

流式的特殊性：`message/stream` 的审计在生成器收尾处写，**对端断连取消也要留痕**
（`outcome="canceled"`）—— 请求作用域会话此时早已提交释放（见 `2026-09-18-a2a-message-stream-design.md`
§3.5），故必须独立会话。

边界（消除歧义）：

- 审计只覆盖**进入方法分发**的调用。被限流拦下的请求不写 `aud_logs`（它没有 `outcome` 可表达，且属于
  风控语域），只写 `RiskEvent`；两者由 `a2a_rate_limit` 事件与 `apiKeyId` 关联。
- 鉴权失败（401/403）在 dep 内抛出，早于视图，**不落本审计、也不落风控**（见 §5）。

### 3.7 运营面改动

- `miles_admin/app_ops/schemas/risk.py`：`RateLimitRuleCreate` / `Update` / `Out` 加
  `scope: Literal["ip", "api_key"]`（Create 默认 `"ip"`）。
  **不引入新枚举类**：`Literal` 在 OpenAPI 里落「属性级 inline enum」，而
  `tests/models/test_api_enum_parity.py` 的平价守卫只看顶层组件（快照实测：顶层带 `enum` 19 个 /
  属性级 inline 7 个），故**不触发**「21 个枚举」相关的 CASES 与白名单改动。
- `miles_admin/app_ops/services/risk.py`：`create` / `update` 已走 `body.model_dump()` 与 `exclude_unset`，
  无需改动（`scope` 随之下传），但需确认 `update` 传 `scope` 后仍 `invalidate_cache()`。
- `ui/admin/features/risk/components/RiskRateLimitEditDialog.tsx` 加 `scope` 选择项（IP / API Key）；
  `RiskRateLimitSection.tsx` 列表加一列。`lib/risk-page-shared.ts` 补文案映射。
- `miles_portal/tenant/audit_log/meta.py`：`ACTION_FILTER_OPTIONS` 登记上述 5 个 action（否则租户审计页
  的下拉筛不到，只能靠手输 action 值；未知 action 本就回显原值）。
- 文档：`docs/guides/a2a.md` 补「限流（按 Key、429 形状、`-32000`）」与「审计（action 清单、不记正文）」
  两小节；`docs/features/a2a-interconnect.md` 同步一句。

### 3.8 迁移

`backend/alembic/versions/003_adm_rate_limit_rules_scope.py`：

```sql
ALTER TABLE adm_rate_limit_rules ADD COLUMN IF NOT EXISTS scope VARCHAR(16) NOT NULL DEFAULT 'ip'
```

`IF NOT EXISTS` 沿用 002 的理由：新库经 001 的 `create_all` 已按 ORM 建出该列，重复执行需为 no-op。
`downgrade` 为 `DROP COLUMN IF EXISTS`。

### 3.9 失败姿态

**Redis 不可用时 fail-open**（放行 + 记错误日志）。取舍是明说的：平台对外 A2A 端点因 Redis 抖动而
全量 5xx/429，代价大于短时限流失效 —— 限流是保护措施，不是正确性依赖。
（现状中间件在 Redis 异常时也是抛出，本批把 A2A 路径的检查包进 `try/except` 以保证 fail-open；中间件
自身的异常姿态不在本批范围。）

## 4. 测试

**纯逻辑 / 单元**：
- `check_rate_limit` 的 `scope` 过滤：`ip` 规则不参与 `api_key` 维度的计数，反之亦然；
- `RateLimitHit.retry_after_seconds` 边界：窗口刚开（≈60）与窗口将尽（≥1，且不为 0）；
- `jsonrpc_error` 带 `data` 与不带 `data` 两种形状（后者与现状逐字一致）；
- 桶键形态：不含 Key 明文/哈希。

**用例层**：
- A2A 限流：未超限放行；超限返回 hit 并写 `RiskEvent`（含 `apiKeyId`）；Redis 抛异常时 fail-open 放行；
- 审计：五种 action 各一条；`message/stream` 对端断连时 `outcome="canceled"` 仍留痕；
- 审计写失败（会话/DB 抛错）不影响业务返回。

**API 层**：
- `POST` 超限 → HTTP 429 + `Retry-After` + JSON-RPC 信封（`code=-32000`、`error.data.retryAfterSeconds`）；
- `message/stream` 超限 → **不进 SSE**，回 `application/json`；
- 产物下载超限 → 429 + `Retry-After` + 平台信封；
- **回归**：存量 `scope='ip'` 规则经中间件仍按 IP 生效。

**迁移**：`make init-db` 后新列存在且默认 `'ip'`；`make verify-db` 通过。

**质量门**：`make lint-backend format-check-backend layers-check openapi-check test-backend`。
预期 OpenAPI 快照**有变化**（新字段 `scope`），需 `make openapi-write` 后再校验。

**分层约束注意**：`miles_openapi.views` 与 `miles_admin.app_ops.schemas` 均受 `api-layer-no-orm` 约束，
`scope` 一律用 `Literal` / `str` 表达，**不得**从 `miles_core.models.risk` 引入枚举类。

## 5. 本批明确不做

- **并发上限（concurrency controls）**：规范 §11 同时也提了它。速率限流已给并发一个上界（每分钟新开数
  × 持续时长），单列一批更稳（要处理计数泄漏与实例宕机回收）。
- **鉴权失败落风控**：`require_agent_api_key` 被 `open_chat` 共用，在该 dep 内加 `RiskEvent` 会改掉聊天
  通路的语义（外部对端拿错 Key 试 A2A 与用户聊天鉴权失败是两回事），要做得单独设计。
- 对端级配额 / 计费、告警通知、限流的运营可视化图表。
- Card GET 的按 Key 限流：Card 是公开发现端点（`fetch_agent_card` 不带凭证），无 Key 可依，只能由
  中间件的 `ip` 规则兜。
