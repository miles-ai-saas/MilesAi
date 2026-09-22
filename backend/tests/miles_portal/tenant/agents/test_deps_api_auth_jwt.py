"""require_agent_chat_auth：JWT 路径需传入 Request。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from miles_core.security import create_access_token
from miles_portal.tenant.agents import deps_api_auth


@pytest.mark.asyncio
async def test_require_agent_chat_auth_jwt_passes_request():
    agent_id = uuid4()
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(
        str(user_id),
        {"tenant_id": str(tenant_id), "purpose": "agent_api_debug"},
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = MagicMock()
    user.id = user_id
    user.tenant_id = tenant_id
    user.username = "u"
    user.is_superuser = False
    role = MagicMock()
    perm = MagicMock()
    perm.code = "agent:read"
    role.permissions = [perm]
    user.roles = [role]

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.access_jti = "jti-from-state"
    db = AsyncMock()

    with patch.object(
        deps_api_auth,
        "get_current_user",
        new_callable=AsyncMock,
        return_value=user,
    ) as mock_gcu:
        ctx = await deps_api_auth.require_agent_chat_auth(
            agent_id=agent_id,
            request=request,
            x_api_key=None,
            credentials=creds,
            db=db,
        )

    mock_gcu.assert_awaited_once()
    assert mock_gcu.await_args.kwargs["request"] is request
    assert ctx.token_jti == "jti-from-state"
    assert ctx.auth_via == "debug_token"
    assert "agent:read" in ctx.permissions
