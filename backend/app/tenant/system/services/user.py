"""租户用户 CRUD 与角色绑定。"""

from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.core.tenant import TenantContext, assert_tenant_access, resolve_tenant_id, tenant_filters
from app.models.user import User
from app.tenant.audit_log.services.audit_log import write_tenant_audit_log
from app.tenant.system.repositories.user import UserRepository
from app.common.schema import PageParams, PageResult
from app.tenant.system.schemas.user import UserBatchRequest, UserCreate, UserOut, UserUpdate
from app.core.soft_delete import is_marked_deleted, mark_deleted
from app.core.service import BaseService
from app.tenant.auth.services.auth import AuthService


def to_user_out(user: User) -> UserOut:
    """ORM User（含 roles）转 API 输出。"""
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
    """租户用户管理；create 时 resolve_tenant_id 限制非超管只能建本租户用户。"""

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

    async def create_user(
        self, body: UserCreate, *, request: Request | None = None
    ) -> UserOut:
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
        await write_tenant_audit_log(
            self.db,
            self.ctx,
            action="user.create",
            resource_type="user",
            resource_id=str(user.id),
            request=request,
            detail={"username": user.username},
        )
        return to_user_out(user)

    async def update_user(
        self, user_id: UUID, body: UserUpdate, *, request: Request | None = None
    ) -> UserOut:
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
        await write_tenant_audit_log(
            self.db,
            self.ctx,
            action="user.update",
            resource_type="user",
            resource_id=str(user.id),
            request=request,
            detail={"fields": list(body.model_dump(exclude_unset=True).keys())},
        )
        return to_user_out(user)

    async def reset_password(
        self, user_id: UUID, password: str, *, request: Request | None = None
    ) -> UserOut:
        user = await self.repo.get_with_roles(user_id)
        if not user or is_marked_deleted(user):
            raise NotFoundError("用户不存在")
        assert_tenant_access(self.ctx, user.tenant_id)
        if len(password) < 6:
            raise BadRequestError("密码至少 6 位")
        user.hashed_password = hash_password(password)
        await self.db.flush()
        await AuthService(self.db, self.ctx).admin_revoke_user_sessions(user.id)
        await write_tenant_audit_log(
            self.db,
            self.ctx,
            action="user.reset_password",
            resource_type="user",
            resource_id=str(user.id),
            request=request,
        )
        await self.db.refresh(user, ["roles"])
        return to_user_out(user)

    async def get_user_or_raise(self, user_id: UUID) -> User:
        user = await self.repo.get_with_roles(user_id)
        if not user or is_marked_deleted(user):
            raise NotFoundError("用户不存在")
        assert_tenant_access(self.ctx, user.tenant_id)
        return user

    async def deactivate_user(
        self, user_id: UUID, *, request: Request | None = None
    ) -> UserOut:
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
        await AuthService(self.db, self.ctx).admin_revoke_user_sessions(user.id)
        await write_tenant_audit_log(
            self.db,
            self.ctx,
            action="user.deactivate",
            resource_type="user",
            resource_id=str(user.id),
            request=request,
        )
        await self.db.refresh(user, ["roles"])
        return to_user_out(user)

    async def batch_deactivate(
        self, user_ids: list[UUID], *, request: Request | None = None
    ) -> dict:
        deactivated = 0
        skipped = 0
        for uid in user_ids:
            if uid == self.ctx.user_id:
                skipped += 1
                continue
            user = await self.repo.get_with_roles(uid)
            if not user or is_marked_deleted(user) or not user.is_active:
                skipped += 1
                continue
            try:
                assert_tenant_access(self.ctx, user.tenant_id)
            except ForbiddenError:
                skipped += 1
                continue
            user.is_active = False
            suffix = user.id.hex[:8]
            user.username = f"{user.username}__deleted__{suffix}"
            user.email = f"deleted+{suffix}+{user.email}"
            await mark_deleted(self.db, user)
            await AuthService(self.db, self.ctx).admin_revoke_user_sessions(user.id)
            await write_tenant_audit_log(
                self.db,
                self.ctx,
                action="user.deactivate",
                resource_type="user",
                resource_id=str(user.id),
                request=request,
                detail={"batch": True},
            )
            deactivated += 1
        return {"deactivated": deactivated, "skipped": skipped}

    async def batch_apply(
        self, body: UserBatchRequest, *, request: Request | None = None
    ) -> dict:
        """批量启用/禁用、赋角色或软删。"""
        if body.action == "deactivate":
            return await self.batch_deactivate(body.user_ids, request=request)

        processed = 0
        skipped = 0
        roles = None
        if body.action == "assign_roles" and body.role_ids is not None:
            roles = await self.repo.load_roles(body.role_ids)

        for uid in body.user_ids:
            if uid == self.ctx.user_id and body.action in ("disable", "deactivate"):
                skipped += 1
                continue
            user = await self.repo.get_with_roles(uid)
            if not user or is_marked_deleted(user):
                skipped += 1
                continue
            try:
                assert_tenant_access(self.ctx, user.tenant_id)
            except ForbiddenError:
                skipped += 1
                continue

            if body.action == "enable":
                if not user.is_active:
                    user.is_active = True
                    await write_tenant_audit_log(
                        self.db,
                        self.ctx,
                        action="user.update",
                        resource_type="user",
                        resource_id=str(user.id),
                        request=request,
                        detail={"batch": True, "is_active": True},
                    )
                    processed += 1
                else:
                    skipped += 1
            elif body.action == "disable":
                if user.is_active:
                    user.is_active = False
                    await AuthService(self.db, self.ctx).admin_revoke_user_sessions(user.id)
                    await write_tenant_audit_log(
                        self.db,
                        self.ctx,
                        action="user.update",
                        resource_type="user",
                        resource_id=str(user.id),
                        request=request,
                        detail={"batch": True, "is_active": False},
                    )
                    processed += 1
                else:
                    skipped += 1
            elif body.action == "assign_roles" and roles is not None:
                user.roles = list(roles)
                await write_tenant_audit_log(
                    self.db,
                    self.ctx,
                    action="user.update",
                    resource_type="user",
                    resource_id=str(user.id),
                    request=request,
                    detail={"batch": True, "role_ids": [str(r) for r in body.role_ids or []]},
                )
                processed += 1

        await self.db.flush()
        return {"processed": processed, "skipped": skipped, "action": body.action}
