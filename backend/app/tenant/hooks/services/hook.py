from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.tenant.hooks.models import HookBinding, HookDefinition
from app.tenant.hooks.schemas.hook import (
    HookBindingCreate,
    HookBindingOut,
    HookDefinitionCreate,
    HookDefinitionOut,
    HookDefinitionUpdate,
)
from app.common.schema import PageParams, PageResult
from app.common.exceptions import NotFoundError
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, mark_deleted_where, not_deleted
from app.core.service import BaseService


class HookService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _get_hook_or_raise(self, hook_id: UUID) -> HookDefinition:
        hook = await self.db.get(HookDefinition, hook_id)
        if not hook or is_marked_deleted(hook):
            raise NotFoundError("钩子不存在")
        assert_tenant_access(self.ctx, hook.tenant_id)
        return hook

    async def list_hooks(self, params: PageParams) -> PageResult[HookDefinitionOut]:
        filters = append_not_deleted(tenant_filters(self.ctx, HookDefinition.tenant_id), HookDefinition)
        total = await self.db.scalar(
            select(func.count()).select_from(HookDefinition).where(*filters)
        )
        stmt = (
            select(HookDefinition)
            .where(*filters)
            .order_by(HookDefinition.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[HookDefinitionOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_hook(self, body: HookDefinitionCreate) -> HookDefinitionOut:
        hook = HookDefinition(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            hook_type=body.hook_type,
            config=body.config,
        )
        self.db.add(hook)
        await self.db.flush()
        binding = HookBinding(
            tenant_id=self.ctx.tenant_id,
            hook_id=hook.id,
            scope=body.scope,
            target_id=body.target_id,
            trigger=body.trigger,
            priority=body.priority,
        )
        self.db.add(binding)
        await self.db.flush()
        await self.db.refresh(hook)
        return HookDefinitionOut.model_validate(hook)

    async def update_hook(self, hook_id: UUID, body: HookDefinitionUpdate) -> HookDefinitionOut:
        hook = await self._get_hook_or_raise(hook_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(hook, k, v)
        await self.db.flush()
        await self.db.refresh(hook)
        return HookDefinitionOut.model_validate(hook)

    async def delete_hook(self, hook_id: UUID) -> None:
        hook = await self._get_hook_or_raise(hook_id)
        await mark_deleted_where(
            self.db,
            HookBinding,
            HookBinding.hook_id == hook.id,
            HookBinding.tenant_id == self.ctx.tenant_id,
        )
        await mark_deleted(self.db, hook)

    async def list_bindings(self, hook_id: UUID) -> list[HookBindingOut]:
        await self._get_hook_or_raise(hook_id)
        rows = (
            await self.db.execute(
                select(HookBinding)
                .where(
                    HookBinding.hook_id == hook_id,
                    HookBinding.tenant_id == self.ctx.tenant_id,
                    not_deleted(HookBinding),
                )
                .order_by(HookBinding.priority.asc())
            )
        ).scalars().all()
        return [HookBindingOut.model_validate(b) for b in rows]

    async def create_binding(self, hook_id: UUID, body: HookBindingCreate) -> HookBindingOut:
        await self._get_hook_or_raise(hook_id)
        binding = HookBinding(
            tenant_id=self.ctx.tenant_id,
            hook_id=hook_id,
            scope=body.scope,
            target_id=body.target_id,
            trigger=body.trigger,
            priority=body.priority,
        )
        self.db.add(binding)
        await self.db.flush()
        await self.db.refresh(binding)
        return HookBindingOut.model_validate(binding)

    async def delete_binding(self, binding_id: UUID) -> None:
        binding = await self.db.get(HookBinding, binding_id)
        if not binding or binding.tenant_id != self.ctx.tenant_id or is_marked_deleted(binding):
            raise NotFoundError("绑定不存在")
        await mark_deleted(self.db, binding)
