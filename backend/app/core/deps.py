"""FastAPI 依赖注入：认证、分页、权限。

租户 API 通过 require_permissions 声明 RBAC；运营端使用 admin.app_sys.deps。
"""

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db import get_db
from app.common.exceptions import UnauthorizedError
from app.core.security import safe_decode_token
from app.core.tenant import TenantContext
from app.models.role import Role
from app.models.user import User
from app.common.schema import PageParams

bearer_scheme = HTTPBearer(auto_error=False)


async def get_page_params(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(50, ge=1, le=100, description="每页条数，最大 100"),
) -> PageParams:
    return PageParams(page=page, size=size)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise UnauthorizedError("未提供认证令牌")
    payload = safe_decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("无效或过期的令牌")
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("无效令牌载荷")
    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("用户不存在或已禁用")
    return user


async def get_tenant_context(user: User = Depends(get_current_user)) -> TenantContext:
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


def require_permissions(*required: str):
    """超级用户绕过具体 permission 校验（见 TenantContext.require_permission）。"""
    async def checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        ctx.require_permission(*required)
        return ctx

    return checker
