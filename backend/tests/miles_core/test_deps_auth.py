"""deps：get_current_user 解码一次，get_tenant_context 复用 jti。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from miles_core import deps
from miles_core.security import create_access_token


@pytest.mark.asyncio
async def test_tenant_context_reuses_jti_without_second_decode():
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(str(user_id), {"tenant_id": str(tenant_id)})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = MagicMock()
    user.id = user_id
    user.tenant_id = tenant_id
    user.username = "u"
    user.is_superuser = False
    user.roles = []

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    # 模拟 FastAPI 会注入的 Request；实现里用 Request 参数
    decode_calls: list[str] = []

    real_safe = deps.safe_decode_token

    def counting_decode(t: str):
        decode_calls.append(t)
        return real_safe(t)

    db = AsyncMock()
    # get_current_user 内部 execute → scalar_one_or_none
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)

    with (
        patch.object(deps, "safe_decode_token", side_effect=counting_decode),
        patch.object(deps.session_store, "is_token_blacklisted", AsyncMock(return_value=False)),
        patch.object(deps.session_store, "touch_session", AsyncMock(return_value=True)),
    ):
        # 实现后 get_current_user 应接受 request: Request
        got_user = await deps.get_current_user(credentials=creds, db=db, request=request)
        assert got_user is user
        ctx = await deps.get_tenant_context(user=got_user, request=request)

    assert ctx.token_jti is not None
    assert len(decode_calls) == 1
