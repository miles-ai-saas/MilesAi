"""租户用户登录、JWT 签发与 Redis 会话。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, UnauthorizedError
from app.core.security import decode_token, issue_tokens_for_user, verify_password
from app.core.tenant import TenantContext
from app.models.role import Role
from app.models.user import User
from app.tenant.system.repositories.user import UserRepository
from app.tenant.auth.schemas.auth import LoginRequest, TokenResponse, UserInfo, UserSessionOut
from app.tenant.auth.services import session_store
from app.tenant.audit_log.services.audit_log import write_auth_login_audit
from app.core.service import BaseService


class AuthService(BaseService):
    """access/refresh 双令牌；多设备会话 + jti 黑名单。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext | None = None) -> None:
        super().__init__(db, ctx)
        self.users = UserRepository(db)

    async def login(
        self,
        body: LoginRequest,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> TokenResponse:
        user = await self.users.get_by_username(body.username)
        if not user or not verify_password(body.password, user.hashed_password):
            raise UnauthorizedError("用户名或密码错误")
        if getattr(user, "deleted_at", None) is not None:
            raise UnauthorizedError("用户已删除")
        if not user.is_active:
            raise UnauthorizedError("用户已禁用")
        access, refresh = issue_tokens_for_user(user)
        await session_store.clear_legacy_session(user.id)
        await session_store.register_session(
            user.id, access, user_agent=user_agent, ip=ip
        )
        await write_auth_login_audit(
            self.db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
        )
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def logout(
        self,
        user_id: UUID,
        *,
        access_token: str | None = None,
        current_jti: str | None = None,
    ) -> None:
        if access_token:
            await session_store.blacklist_token(access_token)
        if current_jti:
            await session_store.revoke_session(user_id, current_jti)
        await session_store.clear_legacy_session(user_id)

    async def refresh(
        self,
        refresh_token: str | None,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> TokenResponse:
        if not refresh_token:
            raise BadRequestError("缺少 refresh_token")
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("令牌类型错误")
        user_id = payload.get("sub")
        user = await self.users.get_one(
            User.id == UUID(str(user_id)),
            User.is_active.is_(True),
        )
        if not user:
            raise UnauthorizedError("用户不存在")
        access, new_refresh = issue_tokens_for_user(user)
        await session_store.register_session(
            user.id, access, user_agent=user_agent, ip=ip
        )
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

    async def list_sessions(
        self, user_id: UUID, *, current_jti: str | None = None
    ) -> list[UserSessionOut]:
        rows = await session_store.list_sessions(user_id)
        return [
            UserSessionOut(
                jti=r["jti"],
                user_agent=r.get("user_agent") or None,
                ip=r.get("ip") or None,
                created_at=r.get("created_at") or "",
                last_seen_at=r.get("last_seen_at"),
                is_current=bool(current_jti and r.get("jti") == current_jti),
            )
            for r in rows
        ]

    async def revoke_session(
        self, user_id: UUID, jti: str, *, current_jti: str | None = None
    ) -> None:
        if current_jti and jti == current_jti:
            raise BadRequestError("不能下线当前会话，请使用登出")
        await session_store.revoke_session(user_id, jti)

    async def revoke_other_sessions(self, user_id: UUID, *, keep_jti: str | None) -> int:
        return await session_store.revoke_all_sessions(user_id, keep_jti=keep_jti)

    async def admin_revoke_user_sessions(self, user_id: UUID) -> int:
        return await session_store.revoke_all_sessions(user_id)
