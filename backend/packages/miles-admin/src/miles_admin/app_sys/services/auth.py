"""平台管理员登录、会话（Redis）与改密。

令牌 type=admin_access，与租户 JWT 分离；会话键 admin:session:{id}。
"""

from uuid import UUID

from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_sys.repositories.admin import PlatformAdminRepository
from miles_admin.app_sys.schemas.auth import AdminInfo, AdminLoginRequest, AdminSessionOut, AdminTokenResponse, PasswordChangeRequest
from miles_admin.app_sys.security import create_admin_access_token
from miles_admin.app_sys.session_store import revoke_admin_session
from miles_common.exceptions import BadRequestError, UnauthorizedError
from miles_common.redis_keys import RedisKeys
from miles_core.config import get_settings
from miles_core.infra.redis import get_redis
from miles_core.security import hash_password, verify_password


class AdminAuthService:
    """运营后台 /api/admin/v1 认证，不经过 TenantContext。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PlatformAdminRepository(db)

    async def login(self, body: AdminLoginRequest) -> AdminTokenResponse:
        """签发 admin_access 并写入 Redis jti。"""
        admin = await self.repo.get_by_username(body.username)
        if not admin or not verify_password(body.password, admin.hashed_password):
            raise UnauthorizedError("用户名或密码错误")
        if not admin.is_active:
            raise UnauthorizedError("管理员已禁用")
        token = create_admin_access_token(admin)
        payload = jose_jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[get_settings().jwt_algorithm],
        )
        jti = payload.get("jti", "")
        await get_redis().setex(RedisKeys.admin_session(admin.id), 60 * 60 * 24 * 7, jti or token[:32])
        return AdminTokenResponse(access_token=token)

    async def logout(self, admin_id: UUID) -> None:
        """吊销指定管理员的 Redis 会话。"""
        await revoke_admin_session(admin_id)

    async def get_me(self, admin_id: UUID) -> AdminInfo:
        """返回当前管理员信息，不存在抛 ``NotFoundError``。"""
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        return AdminInfo.model_validate(admin)

    async def change_password(self, admin_id: UUID, body: PasswordChangeRequest) -> None:
        """校验原密码后更新密码，并吊销会话强制重新登录。"""
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        if not verify_password(body.old_password, admin.hashed_password):
            raise BadRequestError("原密码错误")
        admin.hashed_password = hash_password(body.new_password)
        await self.db.flush()
        await revoke_admin_session(admin_id)

    async def list_sessions(self, *, current_admin_id: UUID | None = None) -> list[AdminSessionOut]:
        """扫描 Redis 会话键列出活跃管理员会话，并标记当前会话。"""
        redis = get_redis()
        sessions: list[AdminSessionOut] = []
        async for key in redis.scan_iter(match=RedisKeys.admin_session_scan_pattern()):
            admin_id = key.decode().split(":")[-1] if isinstance(key, bytes) else str(key).split(":")[-1]
            try:
                admin = await self.repo.get_by_id(UUID(admin_id))
                if admin:
                    sessions.append(
                        AdminSessionOut(
                            admin_id=admin.id,
                            username=admin.username,
                            role=admin.role,
                            is_current=current_admin_id == admin.id if current_admin_id else False,
                        )
                    )
            except ValueError:
                continue
        return sessions

    async def revoke_session(self, admin_id: UUID) -> None:
        """强制下线指定管理员会话。"""
        await revoke_admin_session(admin_id)
