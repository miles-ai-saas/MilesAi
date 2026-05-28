"""平台管理员账号治理（仅 super_admin）。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.admin import (
    ADMIN_ROLES,
    AdminResetPasswordRequest,
    PlatformAdminCreate,
    PlatformAdminOut,
    PlatformAdminUpdate,
)
from app.admin.app_sys.repositories.admin import PlatformAdminRepository
from app.admin.app_sys.session_store import revoke_admin_session
from app.admin.models import PlatformAdmin
from app.common.exceptions import BadRequestError, ForbiddenError
from app.common.schema import PageParams, PageResult
from app.core.security import hash_password


class AdminManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PlatformAdminRepository(db)

    def _validate_role(self, role: str) -> None:
        if role not in ADMIN_ROLES:
            raise BadRequestError(f"无效角色，可选: {', '.join(sorted(ADMIN_ROLES))}")

    async def list_admins(self, params: PageParams) -> PageResult[PlatformAdminOut]:
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            order_by=PlatformAdmin.created_at.desc(),
        )
        return PageResult(
            items=[PlatformAdminOut.model_validate(a) for a in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_admin(self, body: PlatformAdminCreate) -> PlatformAdminOut:
        self._validate_role(body.role)
        if await self.repo.get_by_username(body.username):
            raise BadRequestError("用户名已存在")
        admin = await self.repo.create(
            username=body.username.strip(),
            email=body.email,
            display_name=body.display_name,
            hashed_password=hash_password(body.password),
            role=body.role,
            is_active=True,
        )
        await self.db.refresh(admin)
        return PlatformAdminOut.model_validate(admin)

    async def update_admin(
        self,
        admin_id: UUID,
        body: PlatformAdminUpdate,
        *,
        actor_id: UUID,
    ) -> PlatformAdminOut:
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        if body.role is not None:
            self._validate_role(body.role)
            admin.role = body.role
        if body.email is not None:
            admin.email = body.email
        if body.display_name is not None:
            admin.display_name = body.display_name
        if body.is_active is not None:
            if admin_id == actor_id and not body.is_active:
                raise ForbiddenError("不能禁用当前登录账号")
            admin.is_active = body.is_active
            if not body.is_active:
                await revoke_admin_session(admin_id)
        await self.db.flush()
        return PlatformAdminOut.model_validate(admin)

    async def disable_admin(self, admin_id: UUID, *, actor_id: UUID) -> None:
        if admin_id == actor_id:
            raise ForbiddenError("不能禁用当前登录账号")
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        admin.is_active = False
        await revoke_admin_session(admin_id)
        await self.db.flush()

    async def reset_password(self, admin_id: UUID, body: AdminResetPasswordRequest) -> None:
        admin = await self.repo.get_by_id_or_raise(admin_id, label="管理员不存在")
        admin.hashed_password = hash_password(body.new_password)
        await revoke_admin_session(admin_id)
        await self.db.flush()
