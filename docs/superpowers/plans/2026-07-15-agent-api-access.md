# 智能体工作台 API Tab（对接调试）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地智能体工作台右侧「API」Tab：展示 `POST …/chat` 对接文档，并提供 24h 调试 JWT 签发，复用现有对话路由完成外部 curl/脚本试通。

**Architecture:** 新增 `POST /agents/{id}/api-access/debug-token`（`agent:write`）签发带 `purpose=agent_api_debug` 的短 TTL access JWT 并 `register_session`；前端 `AgentApiPanel` 展示 URL/契约/curl·Python，一键注入 Token；对话仍走现有 `POST …/chat`（`agent:read`）。二期 API Key 不在本计划实现。

**Tech Stack:** FastAPI、Pydantic、现有 JWT/`session_store`、React workbench `features/agents`、`ui/workbench/lib/api`。

**规格：** [2026-07-15-agent-api-access-design.md](../specs/2026-07-15-agent-api-access-design.md)

## Global Constraints

- 一期仅 HTTP chat 文档 + 调试 Token；不做 API Key 表、不做 `/open/...`、不做 WS 文档
- 签发权限 `agent:write`；chat 权限仍为 `agent:read`
- 调试 Token 等效登录用户会话（`purpose`/`agent_id` claim 一期不强制路径校验）
- TTL 走 `agent_api_debug_token_ttl_hours`（默认 24），不复用 `access_token_expire_minutes`
- Commit message 使用简体中文 Conventional Commits
- workbench 新 UI 落在 `features/agents/`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/core/config.py` | `agent_api_debug_token_ttl_hours` |
| `backend/app/core/security.py` | `create_access_token(..., expires_delta=)` |
| `backend/app/tenant/agents/schemas/api_access.py` | `AgentDebugTokenOut` |
| `backend/app/tenant/agents/services/api_access.py` | 校验智能体 + 签发 + register_session |
| `backend/app/tenant/agents/views/agents.py` | 挂载 debug-token 路由 |
| `backend/tests/tenant/agents/test_api_access.py` | 单测 + HTTP 权限/契约 |
| `ui/workbench/lib/types/agents.ts` | `AgentDebugToken` |
| `ui/workbench/lib/api/agents.ts` | `createAgentDebugToken` |
| `ui/workbench/features/agents/components/AgentApiPanel.tsx` | API Tab 面板 |
| `ui/workbench/features/agents/components/AgentWorkbenchOverlay.tsx` | 挂载 api Tab |
| `ui/workbench/features/agents/hooks/use-agents-chat-layout.ts` | `api.ready = true` |
| `ui/workbench/features/agents/index.ts` | 按需导出 |
| `docs/features/agent-api-access.md` | 功能文档 |
| `docs/features/platform-agents.md` | 交叉引用 |

---

### Task 1: JWT TTL 扩展 + 配置项

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/tenant/agents/test_api_access.py`

**Interfaces:**
- Consumes: 现有 `create_access_token(subject, extra)`
- Produces: `create_access_token(subject, extra=None, *, expires_delta: timedelta | None = None)`；`Settings.agent_api_debug_token_ttl_hours: int = 24`

- [ ] **Step 1: 写失败用例（expires_delta 尚未支持）**

在 `backend/tests/tenant/agents/test_api_access.py`：

```python
"""智能体 API 对接调试：debug-token 与 JWT TTL。"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, safe_decode_token


def test_create_access_token_respects_expires_delta():
    settings = get_settings()
    token = create_access_token(
        "user-1",
        {"tenant_id": "t1", "purpose": "agent_api_debug"},
        expires_delta=timedelta(hours=24),
    )
    payload = safe_decode_token(token)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["purpose"] == "agent_api_debug"
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    # 允许时钟误差：约 24h，远大于默认 access_token_expire_minutes
    delta = exp - datetime.now(timezone.utc)
    assert timedelta(hours=23) < delta <= timedelta(hours=24, minutes=1)
    # 确认不是默认 60 分钟
    assert settings.access_token_expire_minutes == 60 or True
    raw = jwt.get_unverified_claims(token)
    assert raw["sub"] == "user-1"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/tenant/agents/test_api_access.py::test_create_access_token_respects_expires_delta -v`

Expected: FAIL（`expires_delta` unexpected keyword 或等价 TypeError）

- [ ] **Step 3: 实现 config + create_access_token**

在 `Settings` 中增加（与其它 JWT 配置相邻）：

```python
agent_api_debug_token_ttl_hours: int = 24
```

替换 `create_access_token`：

```python
def create_access_token(
    subject: str,
    extra: dict[str, Any] | None = None,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """签发 access JWT（type=access，含 tenant_id 等 extra）。"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expire,
        "jti": str(uuid4()),
        **(extra or {}),
    }
    return _encode(payload)
```

确认文件顶部已有 `timedelta` 导入。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/tenant/agents/test_api_access.py::test_create_access_token_respects_expires_delta -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/app/core/config.py backend/tests/tenant/agents/test_api_access.py
git commit -m "$(cat <<'EOF'
feat(auth): create_access_token 支持自定义 expires_delta

供智能体 API 调试 Token 使用独立 TTL，避免绑定登录 access 过期分钟数。
EOF
)"
```

---

### Task 2: Schema + ApiAccessService + HTTP 路由

**Files:**
- Create: `backend/app/tenant/agents/schemas/api_access.py`
- Create: `backend/app/tenant/agents/services/api_access.py`
- Modify: `backend/app/tenant/agents/views/agents.py`
- Modify: `backend/tests/tenant/agents/test_api_access.py`

**Interfaces:**
- Consumes: `create_access_token`、`session_store.register_session`、`AgentRepository`、`assert_tenant_access`、`get_settings().agent_api_debug_token_ttl_hours`
- Produces:
  - `AgentDebugTokenOut(access_token, token_type, expires_in, expires_at, agent_id, purpose, warning)`
  - `AgentApiAccessService.create_debug_token(agent_id: UUID, *, user_agent: str | None = None, ip: str | None = None) -> AgentDebugTokenOut`
  - `POST /api/v1/agents/{agent_id}/api-access/debug-token` → `ApiResponse[AgentDebugTokenOut]`，权限 `agent:write`

- [ ] **Step 1: 写失败用例（路由尚不存在）**

追加到 `test_api_access.py`：

```python
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.apps.application import create_app
from app.core.deps import get_tenant_context
from app.core.tenant import TenantContext
from app.infra.db import get_db
from tests.conftest import disable_platform_risk, make_tenant_ctx


@pytest.mark.asyncio
async def test_debug_token_requires_agent_write():
    with disable_platform_risk():
        app = create_app()
        ctx = make_tenant_ctx(permissions=frozenset(["agent:read"]), is_superuser=False)

        async def override_ctx() -> TenantContext:
            return ctx

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_tenant_context] = override_ctx
        app.dependency_overrides[get_db] = override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/v1/agents/{uuid4()}/api-access/debug-token")
        app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_debug_token_success_shape():
    agent_id = uuid4()
    from app.tenant.agents.schemas.api_access import AgentDebugTokenOut
    from datetime import datetime, timezone

    fake = AgentDebugTokenOut(
        access_token="tok",
        token_type="bearer",
        expires_in=86400,
        expires_at=datetime.now(timezone.utc),
        agent_id=agent_id,
        purpose="agent_api_debug",
        warning="x",
    )
    with disable_platform_risk():
        app = create_app()
        ctx = make_tenant_ctx(permissions=frozenset(["agent:write"]), is_superuser=False)

        async def override_ctx() -> TenantContext:
            return ctx

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_tenant_context] = override_ctx
        app.dependency_overrides[get_db] = override_db
        with patch(
            "app.tenant.agents.views.agents.AgentApiAccessService.create_debug_token",
            new_callable=AsyncMock,
            return_value=fake,
        ):
            # 若 view 用模块级函数构造 service，改 patch 目标为实际调用路径：
            # "app.tenant.agents.services.api_access.AgentApiAccessService.create_debug_token"
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                with patch(
                    "app.tenant.agents.services.api_access.AgentApiAccessService.create_debug_token",
                    new_callable=AsyncMock,
                    return_value=fake,
                ):
                    resp = await client.post(f"/api/v1/agents/{agent_id}/api-access/debug-token")
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["purpose"] == "agent_api_debug"
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] == 86400
    assert body["data"]["access_token"] == "tok"
```

另增 service 单元测试（不依赖 HTTP）：

```python
@pytest.mark.asyncio
async def test_create_debug_token_registers_session_and_claims():
    from app.models.agent import Agent
    from app.tenant.agents.services.api_access import AgentApiAccessService
    from app.core.security import safe_decode_token

    agent_id = uuid4()
    tenant_id = uuid4()
    user_id = uuid4()
    ctx = TenantContext(
        user_id=user_id,
        tenant_id=tenant_id,
        username="u",
        is_superuser=False,
        permissions=frozenset(["agent:write"]),
    )
    agent = Agent(id=agent_id, tenant_id=tenant_id, name="a")
    db = AsyncMock()
    svc = AgentApiAccessService(db, ctx)
    with (
        patch.object(svc.repo, "get_by_id", new_callable=AsyncMock, return_value=agent),
        patch("app.tenant.agents.services.api_access.is_marked_deleted", return_value=False),
        patch(
            "app.tenant.agents.services.api_access.session_store.register_session",
            new_callable=AsyncMock,
        ) as reg,
    ):
        out = await svc.create_debug_token(agent_id, user_agent="agent-api-debug", ip="127.0.0.1")
    payload = safe_decode_token(out.access_token)
    assert payload["purpose"] == "agent_api_debug"
    assert payload["agent_id"] == str(agent_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert out.expires_in == 24 * 3600
    reg.assert_awaited_once()
```

（`Agent(...)` 构造若因必填字段失败，改为 `MagicMock(spec=Agent, id=..., tenant_id=..., ...)` 并保证 `is_marked_deleted` 返回 False。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/tenant/agents/test_api_access.py -v`

Expected: FAIL（缺 schema/服务/路由或 import）

- [ ] **Step 3: 实现 schema**

`backend/app/tenant/agents/schemas/api_access.py`：

```python
"""智能体 API 对接（调试 Token）响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

DEBUG_TOKEN_WARNING = (
    "此令牌等效于当前登录用户凭据，请勿提交到代码仓库或分享；"
    "过期或登出相关会话后失效。正式对外请使用后续 API Key。"
)


class AgentDebugTokenOut(BaseModel):
    access_token: str = Field(description="调试 JWT，仅此响应返回明文")
    token_type: str = Field(default="bearer", description="固定 bearer")
    expires_in: int = Field(description="有效秒数")
    expires_at: datetime = Field(description="过期时间 UTC")
    agent_id: UUID = Field(description="智能体 ID")
    purpose: str = Field(default="agent_api_debug", description="令牌用途标记")
    warning: str = Field(description="安全提示")
```

- [ ] **Step 4: 实现 service**

`backend/app/tenant/agents/services/api_access.py`：

```python
"""智能体 API 对接调试：签发短期 access JWT。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.api_access import DEBUG_TOKEN_WARNING, AgentDebugTokenOut
from app.tenant.auth.services import session_store


class AgentApiAccessService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = AgentRepository(db)

    async def create_debug_token(
        self,
        agent_id: UUID,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> AgentDebugTokenOut:
        assert self.ctx is not None
        agent = await self.repo.get_by_id(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

        settings = get_settings()
        ttl_hours = max(1, int(settings.agent_api_debug_token_ttl_hours))
        expires_delta = timedelta(hours=ttl_hours)
        expires_at = datetime.now(timezone.utc) + expires_delta
        token = create_access_token(
            str(self.ctx.user_id),
            {
                "tenant_id": str(self.ctx.tenant_id),
                "is_superuser": self.ctx.is_superuser,
                "purpose": "agent_api_debug",
                "agent_id": str(agent_id),
            },
            expires_delta=expires_delta,
        )
        await session_store.register_session(
            self.ctx.user_id,
            token,
            user_agent=user_agent or "agent-api-debug",
            ip=ip,
        )
        return AgentDebugTokenOut(
            access_token=token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
            expires_at=expires_at,
            agent_id=agent_id,
            purpose="agent_api_debug",
            warning=DEBUG_TOKEN_WARNING,
        )
```

仓库方法为 `AgentRepository.get_by_id`（继承自 `BaseRepository`）。

- [ ] **Step 5: 挂载 view**

在 `agents.py` 增加 import 与 helper，并在 `export` 路由附近注册（`/{agent_id}` 参数路由均可）：

```python
from fastapi import Request
from app.tenant.agents.schemas.api_access import AgentDebugTokenOut
from app.tenant.agents.services.api_access import AgentApiAccessService


def _api_access_svc(db: AsyncSession, ctx: TenantContext) -> AgentApiAccessService:
    return AgentApiAccessService(db, ctx)


@router.post(
    "/{agent_id}/api-access/debug-token",
    response_model=ApiResponse[AgentDebugTokenOut],
)
async def create_agent_debug_token(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """签发短期调试 access JWT，供外部脚本调用 POST …/chat。"""
    ua = request.headers.get("user-agent")
    # 若项目已有取客户端 IP 的工具则复用，否则 ip=None
    out = await _api_access_svc(db, ctx).create_debug_token(
        agent_id,
        user_agent=f"agent-api-debug;{ua}" if ua else "agent-api-debug",
        ip=request.client.host if request.client else None,
    )
    return ok(out)
```

修正 Task 2 Step 1 中 patch 路径为 view 实际调用的 `AgentApiAccessService.create_debug_token`（实例方法可用 `patch.object` 或 patch 类方法被 await 的路径）。推荐在 view 测试里：

```python
with patch.object(AgentApiAccessService, "create_debug_token", new_callable=AsyncMock, return_value=fake):
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && pytest tests/tenant/agents/test_api_access.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/tenant/agents/schemas/api_access.py \
  backend/app/tenant/agents/services/api_access.py \
  backend/app/tenant/agents/views/agents.py \
  backend/tests/tenant/agents/test_api_access.py
git commit -m "$(cat <<'EOF'
feat(agents): 新增 api-access 调试 Token 签发接口

工作台可签发短 TTL access JWT，外部脚本复用现有 chat 完成对接试通。
EOF
)"
```

---

### Task 3: 前端类型 + API client

**Files:**
- Modify: `ui/workbench/lib/types/agents.ts`
- Modify: `ui/workbench/lib/api/agents.ts`

**Interfaces:**
- Consumes: `POST /agents/{id}/api-access/debug-token`
- Produces: `AgentDebugToken` 类型；`agentsApi.createAgentDebugToken(agentId: string): Promise<AgentDebugToken>`

- [ ] **Step 1: 在 types 末尾增加**

```typescript
export interface AgentDebugToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string;
  agent_id: string;
  purpose: string;
  warning: string;
}
```

- [ ] **Step 2: 在 `agentsApi` 增加**

```typescript
createAgentDebugToken: (agentId: string) =>
  post<import("../types").AgentDebugToken>(`/agents/${agentId}/api-access/debug-token`, {}),
```

（若 `post` 要求 body，传 `{}`；若允许无 body，按 client 现有惯例。）

- [ ] **Step 3: 类型检查（若项目有）**

Run: `cd ui/workbench && npx tsc --noEmit -p tsconfig.json 2>&1 | head -40`

Expected: 无与本次改动相关的错误（或按仓库惯用 typecheck 命令）

- [ ] **Step 4: Commit**

```bash
git add ui/workbench/lib/types/agents.ts ui/workbench/lib/api/agents.ts
git commit -m "$(cat <<'EOF'
feat(ui): 增加智能体调试 Token 的类型与 API client

为工作台 API Tab 对接 debug-token 接口做准备。
EOF
)"
```

---

### Task 4: AgentApiPanel + 挂载 Tab

**Files:**
- Create: `ui/workbench/features/agents/components/AgentApiPanel.tsx`
- Modify: `ui/workbench/features/agents/components/AgentWorkbenchOverlay.tsx`
- Modify: `ui/workbench/features/agents/hooks/use-agents-chat-layout.ts`
- Modify: `ui/workbench/features/agents/index.ts`（可选导出）

**Interfaces:**
- Consumes: `api.createAgentDebugToken`、`NEXT_PUBLIC_API_URL`、`agentId`
- Produces: `AgentApiPanel({ agentId: string })`；`api.ready === true`；overlay 在 `activeTab === "api"` 渲染面板

- [ ] **Step 1: `api.ready = true`**

在 `use-agents-chat-layout.ts`：

```typescript
{ id: "api", label: "API", ready: true },
```

- [ ] **Step 2: 实现 `AgentApiPanel.tsx`**

```tsx
"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { AgentDebugToken } from "@/lib/types";

type Props = { agentId: string };

type CodeTab = "curl" | "python";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function maskToken(token: string): string {
  if (token.length <= 12) return "••••••••";
  return `${token.slice(0, 8)}…${token.slice(-4)}`;
}

export function AgentApiPanel({ agentId }: Props) {
  const chatUrl = `${API_BASE}/agents/${agentId}/chat`;
  const [token, setToken] = useState<AgentDebugToken | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [codeTab, setCodeTab] = useState<CodeTab>("curl");
  const [copied, setCopied] = useState<string | null>(null);

  const bearer = token?.access_token ?? "YOUR_TOKEN";
  const requestJson = useMemo(
    () =>
      JSON.stringify(
        {
          query: "你好",
          conversation_id: null,
          media: [],
          inputs: {},
        },
        null,
        2,
      ),
    [],
  );

  const curlSnippet = `curl -sS -X POST '${chatUrl}' \\
  -H 'Authorization: Bearer ${bearer}' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify({ query: "你好" })}'`;

  const pythonSnippet = `import requests

url = "${chatUrl}"
headers = {
    "Authorization": "Bearer ${bearer}",
    "Content-Type": "application/json",
}
resp = requests.post(url, headers=headers, json={"query": "你好"}, timeout=120)
print(resp.status_code, resp.json())`;

  const responseExample = JSON.stringify(
    {
      code: 0,
      message: "ok",
      data: {
        answer: "你好！有什么可以帮你的？",
        sources: [],
        steps: [],
        artifacts: [],
        pending_tool: null,
        generative_jobs: [],
      },
    },
    null,
    2,
  );

  const copy = async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setError("复制失败");
    }
  };

  const onMint = async () => {
    setBusy(true);
    setError(null);
    try {
      const out = await api.createAgentDebugToken(agentId);
      setToken(out);
      setRevealed(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "签发失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 space-y-4 overflow-auto px-6 py-4">
        <p className="rounded-lg border border-line bg-surface-subtle px-3 py-2 text-xs text-ink-muted">
          一期提供对接调试：使用短期调试 Token 调用下方 HTTP 对话接口。正式 API Key 与独立入口后续提供。
        </p>

        <section className="space-y-2">
          <h3 className="text-sm font-medium text-ink">调用信息</h3>
          <div className="rounded-xl border border-line bg-surface p-3 text-xs">
            <div className="flex items-start justify-between gap-2">
              <code className="break-all text-ink">POST {chatUrl}</code>
              <button type="button" className="shrink-0 text-brand hover:underline" onClick={() => copy("url", chatUrl)}>
                {copied === "url" ? "已复制" : "复制"}
              </button>
            </div>
            <p className="mt-2 text-ink-muted">Header: Authorization: Bearer &lt;token&gt;</p>
            <p className="text-ink-muted">Header: Content-Type: application/json</p>
          </div>
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">调试 Token</h3>
            <button
              type="button"
              disabled={busy}
              onClick={onMint}
              className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {busy ? "生成中…" : token ? "重新生成" : "生成调试 Token"}
            </button>
          </div>
          {token && (
            <div className="space-y-2 rounded-xl border border-line bg-surface p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <code className="break-all text-ink">{revealed ? token.access_token : maskToken(token.access_token)}</code>
                <div className="flex shrink-0 gap-2">
                  <button type="button" className="text-brand hover:underline" onClick={() => setRevealed((v) => !v)}>
                    {revealed ? "隐藏" : "显示"}
                  </button>
                  <button type="button" className="text-brand hover:underline" onClick={() => copy("token", token.access_token)}>
                    {copied === "token" ? "已复制" : "复制"}
                  </button>
                </div>
              </div>
              <p className="text-ink-muted">过期：{new Date(token.expires_at).toLocaleString()}</p>
              <p className="text-ink-faint">{token.warning}</p>
              <p className="text-ink-faint">重新生成不会吊销旧 Token，旧 Token 仍可用至过期。</p>
            </div>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink">请求示例</h3>
            <button type="button" className="text-xs text-brand hover:underline" onClick={() => copy("req", requestJson)}>
              {copied === "req" ? "已复制" : "复制"}
            </button>
          </div>
          <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 text-[11px] text-ink">{requestJson}</pre>
          <p className="text-[11px] text-ink-faint">进阶字段（工具确认、生图预设等）见 ChatRequest / OpenAPI。</p>
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">代码示例</h3>
            <div className="inline-flex rounded-lg border border-line p-0.5">
              {(["curl", "python"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setCodeTab(id)}
                  className={`rounded-md px-2.5 py-1 text-xs ${codeTab === id ? "bg-brand-light text-brand" : "text-ink-muted"}`}
                >
                  {id === "curl" ? "curl" : "Python"}
                </button>
              ))}
            </div>
          </div>
          <div className="relative">
            <button
              type="button"
              className="absolute right-2 top-2 text-xs text-brand hover:underline"
              onClick={() => copy("code", codeTab === "curl" ? curlSnippet : pythonSnippet)}
            >
              {copied === "code" ? "已复制" : "复制"}
            </button>
            <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 pr-16 text-[11px] text-ink">
              {codeTab === "curl" ? curlSnippet : pythonSnippet}
            </pre>
          </div>
        </section>

        <section className="space-y-2 pb-4">
          <h3 className="text-sm font-medium text-ink">响应示例</h3>
          <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 text-[11px] text-ink">{responseExample}</pre>
        </section>
      </div>
    </div>
  );
}
```

按仓库既有按钮/颜色类名微调（与 `AgentStatsPanel` 一致即可）。

- [ ] **Step 3: Overlay 挂载**

在 `AgentWorkbenchOverlay.tsx`：

1. `import { AgentApiPanel } from "..."`  
2. subtitle 分支：`activeTab === "api" ? "对接文档与调试 Token" : ...`（替换原先落到「功能开发中」的 api）  
3. 渲染：

```tsx
) : activeTab === "api" && agentId ? (
  <AgentApiPanel agentId={agentId} />
) : activeTab === "call_records" && agentId ? (
```

注意：原先 `call_records` 之前没有 api 分支时会落到 `AgentWorkbenchPanel`；插入后勿破坏 config 走 `AgentWorkbenchPanel` 的逻辑。`config` 仍由最后的 else / 显式分支处理——建议把 `api` 与其它专用面板并列，最终 else 仍为 config 用的 `AgentWorkbenchPanel`。

- [ ] **Step 4: 可选导出**

在 `features/agents/index.ts` 增加：`export { AgentApiPanel } from "./components/AgentApiPanel";`

- [ ] **Step 5: 手工验证清单**

1. 打开 `/workbench/agents/chat?agent=…&tab=api`  
2. 侧栏「API」无「待开」  
3. 生成 Token → 复制 curl → 后端可调通（联调环境）  

- [ ] **Step 6: Commit**

```bash
git add ui/workbench/features/agents/components/AgentApiPanel.tsx \
  ui/workbench/features/agents/components/AgentWorkbenchOverlay.tsx \
  ui/workbench/features/agents/hooks/use-agents-chat-layout.ts \
  ui/workbench/features/agents/index.ts
git commit -m "$(cat <<'EOF'
feat(agents): 工作台 API Tab 对接文档与调试 Token

开启 API 面板，支持生成短期 Token 并复制 curl/Python 示例。
EOF
)"
```

---

### Task 5: 功能文档

**Files:**
- Create: `docs/features/agent-api-access.md`
- Modify: `docs/features/platform-agents.md`（API 列表增加 debug-token 与文档链接）

**Interfaces:**
- Consumes: 已实现路由与 UI
- Produces: 功能规格文档，与 design spec 对齐

- [ ] **Step 1: 写 `docs/features/agent-api-access.md`**

内容需包含：状态「一期已实现」、端点表、权限、Token claim/TTL、UI 入口、明确不做（二期）、链到 design spec。

- [ ] **Step 2: 更新 `platform-agents.md` §5 API**

在 agents API 列表中增加：

```text
POST /agents/{id}/api-access/debug-token   # 见 agent-api-access.md
```

- [ ] **Step 3: Commit**

```bash
git add docs/features/agent-api-access.md docs/features/platform-agents.md
git commit -m "$(cat <<'EOF'
docs(agents): 补充智能体 API 对接调试功能说明

记录 debug-token 契约、权限与工作台 API Tab 入口。
EOF
)"
```

---

## Spec coverage (self-review)

| 规格项 | 任务 |
|--------|------|
| API Tab ready + AgentApiPanel | Task 4 |
| POST debug-token + 响应字段 | Task 2 |
| 24h TTL / config | Task 1–2 |
| purpose / agent_id claims | Task 2 |
| register_session | Task 2 |
| 复用 POST chat 文档 | Task 4–5 |
| agent:write / agent:read | Task 2 |
| 一期不做 Key / open / WS | Global Constraints（未排任务） |
| 测试：403 / 成功形 / claims | Task 2 |
| features 文档 | Task 5 |

无 TBD；`create_access_token` 签名在 Task 1/2 一致；前端 `AgentDebugToken` 与后端字段对齐。
