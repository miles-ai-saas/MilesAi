"""租户用户登录、JWT 签发与 Redis 会话。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, UnauthorizedError
from app.infra.redis import get_redis
from app.utils.redis_keys import RedisKeys
from app.core.security import decode_token, issue_tokens_for_user, verify_password
from app.core.tenant import TenantContext
from app.models.role import Role
from app.models.user import User
from app.tenant.system.repositories.user import UserRepository
from app.tenant.auth.schemas.auth import LoginRequest, TokenResponse, UserInfo
from app.core.service import BaseService

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


class AuthService(BaseService):
    """access/refresh 双令牌；登出清除 Redis session。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext | None = None) -> None:
        super().__init__(db, ctx)
        self.users = UserRepository(db)

    async def login(self, body: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_username(body.username)
        if not user or not verify_password(body.password, user.hashed_password):
            raise UnauthorizedError("用户名或密码错误")
        if getattr(user, "deleted_at", None) is not None:
            raise UnauthorizedError("用户已删除")
        if not user.is_active:
            raise UnauthorizedError("用户已禁用")
        access, refresh = issue_tokens_for_user(user)
        await get_redis().setex(RedisKeys.session(user.id), SESSION_TTL_SECONDS, access)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def logout(self, user_id: UUID) -> None:
        await get_redis().delete(RedisKeys.session(user_id))

    async def refresh(self, refresh_token: str | None) -> TokenResponse:
        if not refresh_token:
            raise BadRequestError("缺少 refresh_token")
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("令牌类型错误")
        user_id = payload.get("sub")
        user = await self.users.get_one(
            User.id == UUID(str(user_id)),
            User.is_active.is_(True),
        )  # get_one 已排除 deleted_at
        if not user:
            raise UnauthorizedError("用户不存在")
        access, new_refresh = issue_tokens_for_user(user)
        return TokenResponse(access_token=access, refresh_token=new_refresh)

    async def get_me(self, ctx: TenantContext) -> UserInfo:
        result = await self.db.execute(
            select(User)
            .where(User.id == ctx.user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        user = result.scalar_one()
        perms = sorted(ctx.permissions) if not ctx.is_superuser else ["*"]
        return UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            tenant_id=user.tenant_id,
            is_superuser=user.is_superuser,
            permissions=perms,
        )
