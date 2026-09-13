"""FastAPI 依赖注入：认证、分页、权限。

租户 API 通过 require_permissions 声明 RBAC；运营端使用 admin.app_sys.deps。
"""

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_common.exceptions import ForbiddenError, UnauthorizedError
from miles_common.schema import PageParams
from miles_core.auth import session_store
from miles_core.infra.db import get_db
from miles_core.models.platform.role import Role
from miles_core.models.platform.user import User
from miles_core.security import safe_decode_token
from miles_core.tenant import TenantContext

bearer_scheme = HTTPBearer(auto_error=False)


async def get_page_params(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=100, description="每页条数，最大 100"),
) -> PageParams:
    """从 Query 解析分页参数。"""
    return PageParams(page=page, size=size)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Bearer access JWT → 活跃用户（预加载 roles.permissions）。"""
    if not credentials:
        raise UnauthorizedError("未提供认证令牌")
    payload = safe_decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("无效或过期的令牌")
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("无效令牌载荷")
    jti = payload.get("jti")
    if jti and await session_store.is_token_blacklisted(str(jti)):
        raise UnauthorizedError("令牌已失效，请重新登录")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)).options(selectinload(User.roles).selectinload(Role.permissions)))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("用户不存在或已禁用")
    if jti:
        await session_store.touch_session(user.id, str(jti))
    return user


async def get_tenant_context(
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TenantContext:
    """聚合用户角色权限为 TenantContext（/auth/me 与业务 API 共用）。"""
    permissions: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions.add(perm.code)
    token_jti: str | None = None
    if credentials:
        payload = safe_decode_token(credentials.credentials)
        if payload:
            jti = payload.get("jti")
            token_jti = str(jti) if jti else None
    return TenantContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        is_superuser=user.is_superuser,
        permissions=frozenset(permissions),
        token_jti=token_jti,
    )


def require_permissions(*required: str):
    """超级用户绕过具体 permission 校验（见 TenantContext.require_permission）。"""

    async def checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        ctx.require_permission(*required)
        return ctx

    return checker


def require_superuser():
    """仅租户超级管理员可访问（如基础设施连接探测）。"""

    async def checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.is_superuser:
            raise ForbiddenError("仅超级管理员可执行此操作")
        return ctx

    return checker
