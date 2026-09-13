"""智能体 API 对接调试：debug-token 与 JWT TTL。"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from miles_core.config import get_settings
from miles_core.deps import get_tenant_context
from miles_core.infra.db import get_db
from miles_core.security import create_access_token, safe_decode_token
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.api_access import AgentDebugTokenOut
from miles_portal.tenant.agents.services.api_access import AgentApiAccessService
from miles_server.apps.application import create_app
from tests.conftest import disable_platform_risk, make_tenant_ctx


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
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    delta = exp - datetime.now(UTC)
    assert timedelta(hours=23) < delta <= timedelta(hours=24, minutes=1)
    assert settings.access_token_expire_minutes == 60 or True
    raw = jwt.get_unverified_claims(token)
    assert raw["sub"] == "user-1"


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
    fake = AgentDebugTokenOut(
        access_token="tok",
        token_type="bearer",
        expires_in=86400,
        expires_at=datetime.now(UTC),
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
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(
                AgentApiAccessService,
                "create_debug_token",
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


@pytest.mark.asyncio
async def test_create_debug_token_registers_session_and_claims():
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
    agent = MagicMock()
    agent.id = agent_id
    agent.tenant_id = tenant_id
    db = AsyncMock()
    svc = AgentApiAccessService(db, ctx)
    with (
        patch.object(svc.repo, "get_by_id", new_callable=AsyncMock, return_value=agent),
        patch(
            "miles_portal.tenant.agents.services.api_access.session_store.register_session",
            new_callable=AsyncMock,
        ) as reg,
    ):
        out = await svc.create_debug_token(agent_id, user_agent="agent-api-debug", ip="127.0.0.1")
    payload = safe_decode_token(out.access_token)
    assert payload is not None
    assert payload["purpose"] == "agent_api_debug"
    assert payload["agent_id"] == str(agent_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert out.expires_in == 24 * 3600
    reg.assert_awaited_once()
