"""智能体对话：X-API-Key 与 JWT 双通道鉴权。"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_common.constants import AGENT_API_KEY_HEADER
from miles_common.exceptions import ForbiddenError, UnauthorizedError
from miles_core.deps import get_current_user
from miles_core.infra.db import get_db
from miles_core.models.platform.role import Role
from miles_core.models.platform.user import User
from miles_core.security import safe_decode_token
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.repositories.api_key import AgentApiKeyRepository
from miles_portal.tenant.agents.services.api_key_crypto import hash_agent_api_key

bearer_scheme = HTTPBearer(auto_error=False)


async def _ctx_from_api_key(
    *,
    api_key: str,
    agent_id: UUID,
    db: AsyncSession,
) -> TenantContext:
    digest = hash_agent_api_key(api_key.strip())
    keys = AgentApiKeyRepository(db)
    row = await keys.get_by_hash(digest)
    if not row or row.revoked_at is not None:
        raise UnauthorizedError("无效或已吊销的 API Key")
    if row.agent_id != agent_id:
        raise ForbiddenError("API Key 与目标智能体不匹配")
    result = await db.execute(
        select(User).where(User.id == row.created_by, User.is_active.is_(True)).options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("密钥创建者不可用")
    if user.tenant_id != row.tenant_id:
        raise UnauthorizedError("密钥租户不一致")
    await keys.touch_last_used(row)
    return TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=row.id,
    )


async def require_agent_api_key(
    agent_id: UUID,
    x_api_key: str | None = Header(default=None, alias=AGENT_API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """仅接受 X-API-Key（open 路由）。"""
    if not x_api_key or not x_api_key.strip():
        raise UnauthorizedError("缺少 X-API-Key")
    return await _ctx_from_api_key(api_key=x_api_key, agent_id=agent_id, db=db)


async def require_agent_chat_auth(
    agent_id: UUID,
    request: Request,
    x_api_key: str | None = Header(default=None, alias=AGENT_API_KEY_HEADER),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """chat：优先 X-API-Key，否则 JWT（需 agent:read）。"""
    if x_api_key and x_api_key.strip():
        return await _ctx_from_api_key(api_key=x_api_key, agent_id=agent_id, db=db)

    user = await get_current_user(request=request, credentials=credentials, db=db)
    permissions: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
    token_jti = getattr(request.state, "access_jti", None)
    auth_via = "workbench"
    if credentials:
        payload = safe_decode_token(credentials.credentials)
        if payload and payload.get("purpose") == "agent_api_debug":
            auth_via = "debug_token"
    ctx = TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset(permissions),
        token_jti=str(token_jti) if token_jti else None,
        auth_via=auth_via,
    )
    ctx.require_permission("agent:read")
    return ctx
