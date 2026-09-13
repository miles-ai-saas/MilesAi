"""WebSocket 握手鉴权。"""

from __future__ import annotations

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_common.exceptions import UnauthorizedError
from miles_core.models.platform.role import Role
from miles_core.models.platform.user import User
from miles_core.security import safe_decode_token
from miles_core.tenant import TenantContext


def extract_bearer_token(websocket: WebSocket) -> str | None:
    """依次从查询参数 ``token``、``Authorization`` 头提取 Bearer Token。"""
    token = websocket.query_params.get("token")
    if token and token.strip():
        return token.strip()
    auth = websocket.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


async def resolve_tenant_context(db: AsyncSession, token: str) -> TenantContext:
    """校验访问令牌并加载用户角色权限，构造租户上下文；失败抛 ``UnauthorizedError``。"""
    payload = safe_decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("无效或过期的令牌")
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("无效令牌载荷")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)).options(selectinload(User.roles).selectinload(Role.permissions)))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("用户不存在或已禁用")
    permissions: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
    return TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset(permissions),
    )
