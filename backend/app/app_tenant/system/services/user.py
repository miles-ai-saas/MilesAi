from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.security import hash_password
from app.core.tenant import TenantContext, assert_tenant_access, resolve_tenant_id, tenant_filters
from app.models.user import User
from app.app_tenant.system.repositories.user import UserRepository
from app.common.schema import PageParams, PageResult
from app.app_tenant.system.schemas.user import UserCreate, UserOut, UserUpdate
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_codes=[r.code for r in user.roles],
    )


class UserService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = UserRepository(db)

    async def list_users(
        self,
        params: PageParams,
        *,
        tenant_id: UUID | None = None,
    ) -> PageResult[UserOut]:
        filters = tenant_filters(
            self.ctx,
            User.tenant_id,
            requested_tenant_id=tenant_id,
        )
        page = await self.repo.list_with_roles(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=User.created_at.desc(),
        )
        return PageResult(
            items=[to_user_out(u) for u in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_user(self, body: UserCreate) -> UserOut:
        tenant_id = resolve_tenant_id(self.ctx, body.tenant_id)
        await self.repo.ensure_username_unique(body.username)
        user = await self.repo.create(
            tenant_id=tenant_id,
            username=body.username,
            email=body.email,
            phone=body.phone,
            hashed_password=hash_password(body.password),
        )
        if body.role_ids:
            user.roles = await self.repo.load_roles(body.role_ids)
        await self.db.flush()
        await self.db.refresh(user, ["roles"])
        return to_user_out(user)

    async def update_user(self, user_id: UUID, body: UserUpdate) -> UserOut:
        user = await self.repo.get_with_roles(user_id)
        if not user or is_marked_deleted(user):
            raise NotFoundError("用户不存在")
        assert_tenant_access(self.ctx, user.tenant_id)

        data = body.model_dump(exclude_unset=True)
        role_ids = data.pop("role_ids", None)
        await self.repo.update_fields(user, data)
        if role_ids is not None:
            user.roles = await self.repo.load_roles(role_ids)
        await self.db.refresh(user, ["roles"])
        return to_user_out(user)

    async def deactivate_user(self, user_id: UUID) -> UserOut:
        user = await self.repo.get_with_roles(user_id)
        if not user or is_marked_deleted(user):
            raise NotFoundError("用户不存在")
        assert_tenant_access(self.ctx, user.tenant_id)
        if user.id == self.ctx.user_id:
            raise BadRequestError("不能删除当前登录用户")
        user.is_active = False
        suffix = user.id.hex[:8]
        user.username = f"{user.username}__deleted__{suffix}"
        user.email = f"deleted+{suffix}+{user.email}"
        await mark_deleted(self.db, user)
        await self.db.refresh(user, ["roles"])
        return to_user_out(user)
