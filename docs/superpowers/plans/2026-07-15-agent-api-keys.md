# 智能体正式 API Key 与开放调用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为智能体提供可吊销、不过期的 API Key；支持 `X-API-Key` 调用既有 `POST …/chat` 与专用 `POST /open/agents/{id}/chat`；工作台 API Tab 完成密钥管理与正式对接文档。

**Architecture:** 表 `agt_agent_api_keys` 存 hash/prefix；鉴权优先读 `X-API-Key`，映射 `created_by` 为 `TenantContext`；chat 路由改为 JWT 或 Key；open 路由仅 Key 并复用 `AgentService.chat`；调用记录写 `source`。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、Pydantic、现有 `TenantContext`/`require_permissions`、React workbench `features/agents`。

**规格：** [2026-07-15-agent-api-keys-design.md](../specs/2026-07-15-agent-api-keys-design.md)

## Global Constraints

- Header：专用 `X-API-Key`（非 Bearer 传 Key）
- `/agents/{id}/chat`：JWT **或** Key；`/open/agents/{id}/chat`：**仅** Key
- Key 不过期，手动吊销；每 agent 最多 **8** 个 **active** Key
- 明文格式：`mil_<prefix8>_<secret32>`；明文仅创建时返回一次
- Key 身份映射 `created_by`；路径 `agent_id` 必须与 Key 绑定一致
- `X-API-Key` 与 `Authorization` 同时存在时优先 Key
- 不做过期/限流/IP 白名单/WS/全局 Key
- Commit message 使用简体中文 Conventional Commits
- 新 UI 落在 `features/agents/`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/008_agent_api_keys.py` | 建表 + `source` 列（`down_revision="007"`；若链头已变则改指向当前 head） |
| `backend/app/models/agent/api_key.py` | ORM `AgentApiKey` |
| `backend/app/models/agent/__init__.py` | 导出 |
| `backend/app/models/agent/chat_call.py` | 字段 `source` |
| `backend/app/core/tenant.py` | `auth_via` 可选字段 |
| `backend/app/tenant/agents/services/api_key_crypto.py` | 生成明文、hash |
| `backend/app/tenant/agents/repositories/api_key.py` | 查/建/吊销 |
| `backend/app/tenant/agents/schemas/api_access.py` | Key 入出参（扩展现有文件） |
| `backend/app/tenant/agents/services/api_access.py` | debug-token + keys CRUD |
| `backend/app/core/deps.py` 或 `tenant/agents/deps_api_key.py` | `require_agent_api_key` / `require_agent_chat_auth` |
| `backend/app/tenant/agents/views/agents.py` | keys 路由；chat Depends 替换 |
| `backend/app/tenant/agents/views/open_chat.py` | open chat |
| `backend/app/tenant/router.py` | 挂载 `/open` |
| `backend/app/tenant/agents/services/call_records.py` | 写入 `source` |
| `backend/tests/tenant/agents/test_agent_api_keys.py` | 鉴权与 CRUD 测试 |
| `ui/workbench/lib/types/agents.ts` | Key 类型 |
| `ui/workbench/lib/api/agents.ts` | client |
| `ui/workbench/features/agents/components/AgentApiPanel.tsx` | 密钥 UI + 文档 |
| `docs/features/agent-api-access.md` | 二期说明 |

---

### Task 1: 迁移 + ORM

**Files:**
- Create: `backend/alembic/versions/008_agent_api_keys.py`
- Create: `backend/app/models/agent/api_key.py`
- Modify: `backend/app/models/agent/__init__.py`
- Modify: `backend/app/models/agent/chat_call.py`

**Interfaces:**
- Produces: `AgentApiKey` model；`AgentChatCall.source: str | None`

- [ ] **Step 1: 确认 alembic head**

Run: `cd backend && alembic heads`

Expected: 当前 head（撰写计划时为 `007`）。迁移 `down_revision` 必须等于该 head。

- [ ] **Step 2: 写迁移**

```python
"""agent api keys + chat call source

Revision ID: 008
Revises: 007
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"  # 换成 Step 1 的实际 head
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "agt_agent_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_agt_agent_api_keys_tenant_agent", "agt_agent_api_keys", ["tenant_id", "agent_id"])
    op.create_index("uq_agt_agent_api_keys_key_hash", "agt_agent_api_keys", ["key_hash"], unique=True)
    op.add_column("agt_agent_chat_calls", sa.Column("source", sa.String(16), nullable=True))

def downgrade() -> None:
    op.drop_column("agt_agent_chat_calls", "source")
    op.drop_index("uq_agt_agent_api_keys_key_hash", table_name="agt_agent_api_keys")
    op.drop_index("idx_agt_agent_api_keys_tenant_agent", table_name="agt_agent_api_keys")
    op.drop_table("agt_agent_api_keys")
```

- [ ] **Step 3: ORM**

`api_key.py`：继承 `UUIDPrimaryKeyMixin, TimestampMixin, Base`；字段与表一致；`__tablename__ = "agt_agent_api_keys"`。

`chat_call.py` 增加：

```python
source: Mapped[str | None] = mapped_column(String(16), nullable=True)
```

在 `models/agent/__init__.py` 导出 `AgentApiKey`。

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/008_agent_api_keys.py \
  backend/app/models/agent/api_key.py \
  backend/app/models/agent/__init__.py \
  backend/app/models/agent/chat_call.py
git commit -m "$(cat <<'EOF'
feat(agents): 新增 API Key 表与调用记录 source 字段

为正式 X-API-Key 鉴权与来源标记落地存储层。
EOF
)"
```

---

### Task 2: crypto + schemas + keys CRUD service

**Files:**
- Create: `backend/app/tenant/agents/services/api_key_crypto.py`
- Create: `backend/app/tenant/agents/repositories/api_key.py`
- Modify: `backend/app/tenant/agents/schemas/api_access.py`
- Modify: `backend/app/tenant/agents/services/api_access.py`
- Create: `backend/tests/tenant/agents/test_agent_api_keys.py`（先写 crypto / limit 单测）

**Interfaces:**
- Produces:
  - `generate_agent_api_key_secret() -> tuple[plaintext, prefix, hash]`
  - `hash_agent_api_key(plaintext: str) -> str`（`sha256` hex）
  - `AgentApiKeyCreate(name: str)`；`AgentApiKeyOut`；`AgentApiKeyCreatedOut`（含 `secret`）
  - `AgentApiAccessService.create_api_key / list_api_keys / revoke_api_key`
  - 常量 `MAX_ACTIVE_AGENT_API_KEYS = 8`

- [ ] **Step 1: 失败测试 — crypto 格式**

```python
from app.tenant.agents.services.api_key_crypto import (
    generate_agent_api_key_secret,
    hash_agent_api_key,
)

def test_generate_agent_api_key_secret_format():
    plain, prefix, digest = generate_agent_api_key_secret()
    assert plain.startswith("mil_")
    assert plain.count("_") >= 2
    parts = plain.split("_", 2)
    assert parts[0] == "mil"
    assert len(parts[1]) == 8
    assert len(parts[2]) >= 32
    assert prefix == parts[1]
    assert digest == hash_agent_api_key(plain)
    assert len(digest) == 64
```

- [ ] **Step 2: 跑测确认失败 → 实现 crypto → 再跑通**

```python
import hashlib
import secrets
import string

_ALPHABET = string.ascii_letters + string.digits

def hash_agent_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

def _rand(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))

def generate_agent_api_key_secret() -> tuple[str, str, str]:
    prefix = _rand(8)
    secret = _rand(32)
    plain = f"mil_{prefix}_{secret}"
    return plain, prefix, hash_agent_api_key(plain)
```

- [ ] **Step 3: schemas**

在 `api_access.py` 增加 `AgentApiKeyCreate`、`AgentApiKeyOut`（`status: Literal["active","revoked"]`）、`AgentApiKeyCreatedOut(AgentApiKeyOut)` 多 `secret` + `warning`。

- [ ] **Step 4: repository + service 方法**

- `get_by_hash`、`count_active(agent_id)`、`list_by_agent`、`add`、`get_by_id`
- `create_api_key`：校验 agent 租户；active≥8 → `BadRequestError`；写行；返回 `AgentApiKeyCreatedOut`
- `list_api_keys(include_revoked=False)`
- `revoke_api_key`：幂等设 `revoked_at`

- [ ] **Step 5: 单测 create limit（mock repo）或 HTTP 放到 Task 4**

至少保留 crypto 测试通过。

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 实现 API Key 生成与 CRUD 服务

明文仅创建返回；active 密钥数上限 8；库内只存 hash。
EOF
)"
```

---

### Task 3: TenantContext.auth_via + 鉴权依赖

**Files:**
- Modify: `backend/app/core/tenant.py`
- Create: `backend/app/tenant/agents/deps_api_auth.py`（推荐独立，避免 deps.py 膨胀）
- Modify: tests

**Interfaces:**
- Produces:
  - `TenantContext.auth_via: str | None = None`  # `jwt` | `api_key` | `debug_token`
  - `async def resolve_tenant_context_from_api_key(request, db, agent_id) -> TenantContext`
  - `require_agent_api_key(agent_id)` — 仅 Key
  - `require_agent_chat_auth()` — Key 优先，否则 JWT + `agent:read`

- [ ] **Step 1: 扩展 TenantContext**

```python
auth_via: str | None = None
```

更新所有手动构造 `TenantContext(...)` 的测试 fixture（缺省 `None` 即可，dataclass 有默认则无需改）。

- [ ] **Step 2: 实现 deps_api_auth**

逻辑要点：

1. 读 header `X-API-Key`（大小写按 Starlette 规范）  
2. 有则：hash → 查未吊销 → `key.agent_id == agent_id` 否则 `ForbiddenError` → 加载 User → 构造 ctx（`permissions=frozenset({"agent:read"})`，`is_superuser` 取用户，`auth_via="api_key"`）→ `last_used_at=now`  
3. open 无 Key → `UnauthorizedError`  
4. chat 无 Key：走现有 `get_tenant_context` + `require_permission("agent:read")`；若 JWT payload `purpose==agent_api_debug` 则 `auth_via="debug_token"`，否则 `"jwt"` / `"workbench"`——规格用 `workbench` 写 source，建议 **auth_via 取值：`api_key` | `debug_token` | `workbench`**

- [ ] **Step 3: 单测**

- 无效 Key → 401  
- agent 不匹配 → 403  
- 已吊销 → 401  

（可用 AsyncMock repo / patch `get_by_hash`。）

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 增加 X-API-Key 鉴权依赖

支持按智能体绑定校验，并把创建者映射为 TenantContext。
EOF
)"
```

---

### Task 4: HTTP — keys 路由 + chat Depends + open 路由

**Files:**
- Modify: `backend/app/tenant/agents/views/agents.py`
- Create: `backend/app/tenant/agents/views/open_chat.py`
- Modify: `backend/app/tenant/router.py`
- Modify: `backend/tests/tenant/agents/test_agent_api_keys.py`

**Interfaces:**
- `GET/POST /agents/{id}/api-access/keys`、`POST .../keys/{key_id}/revoke`
- `POST /open/agents/{id}/chat`
- `POST /agents/{id}/chat` 改用 `require_agent_chat_auth`

- [ ] **Step 1: 写 HTTP 失败用例（权限 / open 无 Key）**

参照 `test_api_access.py`：override ctx + patch service。

- [ ] **Step 2: 挂路由**

`open_chat.py`：

```python
router = APIRouter()

@router.post("/agents/{agent_id}/chat", response_model=ApiResponse[ChatResponse])
async def open_agent_chat(
    agent_id: UUID,
    body: ChatRequest,
    ctx: TenantContext = Depends(require_agent_api_key),  # 从 path 注入 agent_id
    db: AsyncSession = Depends(get_db),
):
    return ok(await AgentService(db, ctx).chat(agent_id, body))
```

注意：`require_agent_api_key` 需能读取 path 中的 `agent_id`（FastAPI 依赖可声明同名参数）。

`router.py`：

```python
from app.tenant.agents.views import open_chat
api_router.include_router(open_chat.router, prefix="/open", tags=["open-agents"])
```

- [ ] **Step 3: agents.py keys + chat Depends**

将 `chat_agent` 的 `Depends(require_permissions("agent:read"))` 换为 chat auth 依赖。

- [ ] **Step 4: 跑测试 PASS + Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 开放 open chat 与 API Key 管理接口

正式对接走 X-API-Key；工作台可创建与吊销密钥。
EOF
)"
```

---

### Task 5: 调用记录 source

**Files:**
- Modify: `backend/app/tenant/agents/services/call_records.py`
- Modify: `backend/app/core/deps.py` 中 JWT 路径设置 `auth_via`（若 Task 3 未在 get_tenant_context 完成）

**Interfaces:**
- `AgentChatCall.source` ← `ctx.auth_via`（`workbench` | `debug_token` | `api_key`）

- [ ] **Step 1: record_success / record_failure 增加 `source=self.ctx.auth_via`**

- [ ] **Step 2: 确保 JWT `get_tenant_context` 设置 auth_via**

解码 purpose：`agent_api_debug` → `debug_token`；否则 `workbench`。

- [ ] **Step 3: 测试或手动断言构造的 row.source；Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 调用记录写入 source 来源标记

区分工作台、调试 Token 与 API Key 调用。
EOF
)"
```

---

### Task 6: 前端类型、client、AgentApiPanel

**Files:**
- Modify: `ui/workbench/lib/types/agents.ts`
- Modify: `ui/workbench/lib/api/agents.ts`
- Modify: `ui/workbench/features/agents/components/AgentApiPanel.tsx`

**Interfaces:**
- `listAgentApiKeys` / `createAgentApiKey` / `revokeAgentApiKey`
- UI：密钥表 + 创建弹层；主推 open URL + `X-API-Key`；调试 Token 折叠

- [ ] **Step 1: types + api methods**

```typescript
export interface AgentApiKey {
  id: string;
  name: string;
  key_prefix: string;
  status: "active" | "revoked";
  created_at: string;
  last_used_at?: string | null;
}
export interface AgentApiKeyCreated extends AgentApiKey {
  secret: string;
  warning: string;
}
```

- [ ] **Step 2: 改面板布局**

- 顶栏文案改为正式对接  
- Endpoint：`${API_BASE}/open/agents/${agentId}/chat`  
- Header 示例：`X-API-Key: mil_…`  
- 密钥区：名称 input + 创建；列表；吊销确认  
- 创建成功 Modal/内嵌告警展示 `secret`  
- 调试 Token 放入 `<details>` 折叠  

（若本地已有一期样式优化未提交，在本任务一并纳入。）

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): API Tab 支持密钥管理与正式对接文档

主推 open 接口与 X-API-Key；调试 Token 降级为折叠试通区。
EOF
)"
```

---

### Task 7: 功能文档

**Files:**
- Modify: `docs/features/agent-api-access.md`
- Modify: `docs/features/platform-agents.md`（可选一行）

- [ ] **Step 1: 文档标明二期已实现：Key CRUD、open 路径、source；保留一期 debug-token**

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(agents): 更新 API 对接文档以覆盖正式 API Key

补充 open 路由、X-API-Key 与密钥生命周期说明。
EOF
)"
```

---

## Spec coverage (self-review)

| 规格项 | 任务 |
|--------|------|
| 表 + hash/prefix | Task 1–2 |
| source 列 | Task 1、5 |
| CRUD + 上限 8 | Task 2、4 |
| X-API-Key + 双路径 | Task 3–4 |
| open 仅 Key | Task 4 |
| UI 密钥 + 文档 | Task 6 |
| 功能文档 | Task 7 |
| 不做过期/限流 | Global Constraints |

无 TBD；`auth_via`/`source` 枚举与规格一致（`workbench` | `debug_token` | `api_key`）。
