"""角色与权限 CRUD（RBAC permission code 供 require_permissions 使用）。"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.platform.role import Permission, Role
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.system.repositories.role import RoleRepository
from miles_portal.tenant.system.schemas.role import (
    PermissionGroupOut,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
)


def _role_out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        code=role.code,
        description=role.description,
        is_system=role.is_system,
        permission_codes=[p.code for p in role.permissions],
    )


class RoleService(BaseService):
    """租户角色与全局 Permission 目录；系统内置角色 is_system 不可删。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = RoleRepository(db)

    def _tenant_role_filters(self):
        return [
            *tenant_filters(self.ctx, Role.tenant_id),
            not_deleted(Role),
        ]

    async def list_permissions(self) -> list[PermissionGroupOut]:
        """按模块分组返回全部未软删权限。"""
        rows = (await self.db.execute(select(Permission).where(not_deleted(Permission)).order_by(Permission.module, Permission.code))).scalars().all()
        groups: dict[str, list[PermissionOut]] = {}
        for p in rows:
            groups.setdefault(p.module, []).append(PermissionOut.model_validate(p))
        return [PermissionGroupOut(module=m, permissions=perms) for m, perms in sorted(groups.items())]

    async def list_roles(self, params: PageParams) -> PageResult[RoleOut]:
        """分页返回本租户角色（系统角色优先），预加载权限。"""
        filters = self._tenant_role_filters()
        total = await self.db.scalar(select(func.count(Role.id)).where(*filters))
        stmt = (
            select(Role)
            .where(*filters)
            .options(selectinload(Role.permissions))
            .order_by(Role.is_system.desc(), Role.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[_role_out(r) for r in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def list_assignable_roles(self) -> list[RoleOut]:
        """用户表单下拉：本租户角色 + 全局系统角色（只读分配）。"""
        filters = [
            not_deleted(Role),
            or_(Role.tenant_id == self.ctx.tenant_id, Role.tenant_id.is_(None)),
        ]
        stmt = select(Role).where(*filters).options(selectinload(Role.permissions)).order_by(Role.name)
        items = (await self.db.execute(stmt)).scalars().all()
        return [_role_out(r) for r in items]

    async def _get_role_or_raise(self, role_id: UUID) -> Role:
        role = await self.repo.get_with_permissions(role_id)
        if not role or is_marked_deleted(role):
            raise NotFoundError("角色不存在")
        if role.tenant_id is not None:
            assert_tenant_access(self.ctx, role.tenant_id)
        return role

    async def create_role(self, body: RoleCreate) -> RoleOut:
        """创建租户内角色；code 在租户内唯一，冲突抛 BadRequestError。"""
        code = body.code.strip()
        existing = await self.db.scalar(
            select(Role).where(
                Role.code == code,
                Role.tenant_id == self.ctx.tenant_id,
                not_deleted(Role),
            )
        )
        if existing:
            raise BadRequestError("角色编码已存在")
        role = Role(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            code=code,
            description=body.description,
            is_system=False,
        )
        self.db.add(role)
        await self.db.flush()
        if body.permission_ids:
            role.permissions = await self.repo.load_permissions(body.permission_ids)
        await self.db.flush()
        await self.db.refresh(role, ["permissions"])
        return _role_out(role)

    async def update_role(self, role_id: UUID, body: RoleUpdate) -> RoleOut:
        """更新角色；系统内置或跨租户角色拒绝修改（抛 BadRequestError）。"""
        role = await self._get_role_or_raise(role_id)
        if role.is_system or role.tenant_id is None:
            raise BadRequestError("系统内置角色不可修改")
        if role.tenant_id != self.ctx.tenant_id:
            raise BadRequestError("无权修改该角色")
        data = body.model_dump(exclude_unset=True)
        perm_ids = data.pop("permission_ids", None)
        for k, v in data.items():
            setattr(role, k, v)
        if perm_ids is not None:
            role.permissions = await self.repo.load_permissions(perm_ids)
        await self.db.flush()
        await self.db.refresh(role, ["permissions"])
        return _role_out(role)

    async def delete_role(self, role_id: UUID) -> None:
        """软删租户角色；系统内置或跨租户角色拒绝删除。"""
        role = await self._get_role_or_raise(role_id)
        if role.is_system or role.tenant_id is None:
            raise BadRequestError("系统内置角色不可删除")
        if role.tenant_id != self.ctx.tenant_id:
            raise BadRequestError("无权删除该角色")
        await mark_deleted(self.db, role)
