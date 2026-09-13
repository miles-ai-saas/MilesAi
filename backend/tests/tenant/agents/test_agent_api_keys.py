"""智能体正式 API Key：crypto 与鉴权。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import ForbiddenError, UnauthorizedError
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.deps_api_auth import _ctx_from_api_key
from miles_portal.tenant.agents.services.api_key_crypto import generate_agent_api_key_secret, hash_agent_api_key


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


@pytest.mark.asyncio
async def test_ctx_from_api_key_agent_mismatch():
    agent_id = uuid4()
    other = uuid4()
    plain, _, _digest = generate_agent_api_key_secret()
    row = MagicMock()
    row.revoked_at = None
    row.agent_id = other
    row.tenant_id = uuid4()
    row.created_by = uuid4()
    db = AsyncMock()
    with patch(
        "miles_portal.tenant.agents.deps_api_auth.AgentApiKeyRepository.get_by_hash",
        new_callable=AsyncMock,
        return_value=row,
    ):
        with pytest.raises(ForbiddenError):
            await _ctx_from_api_key(api_key=plain, agent_id=agent_id, db=db)


@pytest.mark.asyncio
async def test_ctx_from_api_key_revoked():
    agent_id = uuid4()
    plain, _, _ = generate_agent_api_key_secret()
    row = MagicMock()
    row.revoked_at = datetime.now(UTC)
    row.agent_id = agent_id
    db = AsyncMock()
    with patch(
        "miles_portal.tenant.agents.deps_api_auth.AgentApiKeyRepository.get_by_hash",
        new_callable=AsyncMock,
        return_value=row,
    ):
        with pytest.raises(UnauthorizedError):
            await _ctx_from_api_key(api_key=plain, agent_id=agent_id, db=db)


@pytest.mark.asyncio
async def test_ctx_from_api_key_success():
    agent_id = uuid4()
    tenant_id = uuid4()
    user_id = uuid4()
    plain, _, _ = generate_agent_api_key_secret()
    row = MagicMock()
    row.revoked_at = None
    row.agent_id = agent_id
    row.tenant_id = tenant_id
    row.created_by = user_id
    user = MagicMock()
    user.id = user_id
    user.tenant_id = tenant_id
    user.username = "u"
    user.is_superuser = False
    user.roles = []
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    with (
        patch(
            "miles_portal.tenant.agents.deps_api_auth.AgentApiKeyRepository.get_by_hash",
            new_callable=AsyncMock,
            return_value=row,
        ),
        patch(
            "miles_portal.tenant.agents.deps_api_auth.AgentApiKeyRepository.touch_last_used",
            new_callable=AsyncMock,
        ),
    ):
        ctx = await _ctx_from_api_key(api_key=plain, agent_id=agent_id, db=db)
    assert isinstance(ctx, TenantContext)
    assert ctx.auth_via == "api_key"
    assert ctx.user_id == user_id
    assert "agent:read" in ctx.permissions
