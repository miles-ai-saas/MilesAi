from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_sys.repositories.admin import PlatformAdminRepository
from app.admin.app_sys.security import create_admin_access_token
from app.common.exceptions import BadRequestError, UnauthorizedError
from app.infra.redis import get_redis
from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.admin.app_sys.schemas.auth import AdminInfo, AdminLoginRequest, AdminSessionOut, AdminTokenResponse, PasswordChangeRequest

ADMIN_SESSION_PREFIX = "admin:session:"


class AdminAuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PlatformAdminRepository(db)

    async def login(self, body: AdminLoginRequest) -> AdminTokenResponse:
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
        await get_redis().setex(f"{ADMIN_SESSION_PREFIX}{admin.id}", 60 * 60 * 24 * 7, jti or token[:32])
        return AdminTokenResponse(access_token=token)

    async def logout(self, admin_id: UUID) -> None:
        await get_redis().delete(f"{ADMIN_SESSION_PREFIX}{admin_id}")

    async def get_me(self, admin_id: UUID) -> AdminInfo:
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        return AdminInfo.model_validate(admin)

    async def change_password(self, admin_id: UUID, body: PasswordChangeRequest) -> None:
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        if not verify_password(body.old_password, admin.hashed_password):
            raise BadRequestError("原密码错误")
        admin.hashed_password = hash_password(body.new_password)
        await self.db.flush()

    async def list_sessions(self) -> list[AdminSessionOut]:
        redis = get_redis()
        sessions: list[AdminSessionOut] = []
        async for key in redis.scan_iter(match=f"{ADMIN_SESSION_PREFIX}*"):
            admin_id = key.decode().split(":")[-1] if isinstance(key, bytes) else str(key).split(":")[-1]
            try:
                admin = await self.repo.get_by_id(UUID(admin_id))
                if admin:
                    sessions.append(
                        AdminSessionOut(
                            admin_id=admin.id,
                            username=admin.username,
                            role=admin.role,
                        )
                    )
            except ValueError:
                continue
        return sessions

    async def revoke_session(self, admin_id: UUID) -> None:
        await get_redis().delete(f"{ADMIN_SESSION_PREFIX}{admin_id}")
