"""平台运营后台依赖：管理员认证。"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.common.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import safe_decode_token
from app.admin.models import PlatformAdmin

admin_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminContext:
    admin_id: UUID
    username: str
    role: str


async def get_platform_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
    db: AsyncSession = Depends(get_db),
) -> AdminContext:
    if not credentials:
        raise UnauthorizedError("未提供管理员令牌")
    payload = safe_decode_token(credentials.credentials)
    if not payload or payload.get("type") != "admin_access":
        raise UnauthorizedError("无效的管理员令牌")
    admin_id = payload.get("sub")
    if not admin_id:
        raise UnauthorizedError("无效令牌载荷")
    admin = await db.scalar(
        select(PlatformAdmin).where(
            PlatformAdmin.id == UUID(str(admin_id)),
            PlatformAdmin.is_active.is_(True),
        )
    )
    if not admin:
        raise UnauthorizedError("管理员不存在或已禁用")
    request.state.admin_ctx = AdminContext(
        admin_id=admin.id, username=admin.username, role=admin.role
    )
    return request.state.admin_ctx


def require_admin_role(*roles: str):
    async def checker(ctx: AdminContext = Depends(get_platform_admin)) -> AdminContext:
        if roles and ctx.role not in roles and ctx.role != "super_admin":
            raise ForbiddenError(f"需要角色: {', '.join(roles)}")
        return ctx

    return checker
