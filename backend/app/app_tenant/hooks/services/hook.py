from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, tenant_filters
from app.app_tenant.hooks.models import HookBinding, HookDefinition
from app.app_tenant.hooks.schemas.hook import (
    HookBindingCreate,
    HookBindingOut,
    HookDefinitionCreate,
    HookDefinitionOut,
    HookDefinitionUpdate,
)
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService


class HookService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _get_hook_or_raise(self, hook_id: UUID) -> HookDefinition:
        from app.core.tenant import assert_tenant_access

        hook = await self.db.get(HookDefinition, hook_id)
        if not hook:
            raise NotFoundError("钩子不存在")
        assert_tenant_access(self.ctx, hook.tenant_id)
        return hook

    async def list_hooks(self, params: PageParams) -> PageResult[HookDefinitionOut]:
        filters = tenant_filters(self.ctx, HookDefinition.tenant_id)
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
        await self.repo_update(hook, body.model_dump(exclude_unset=True))
        await self.db.refresh(hook)
        return HookDefinitionOut.model_validate(hook)

    async def repo_update(self, hook: HookDefinition, data: dict) -> None:
        for k, v in data.items():
            setattr(hook, k, v)
        await self.db.flush()

    async def delete_hook(self, hook_id: UUID) -> None:
        hook = await self._get_hook_or_raise(hook_id)
        bindings = (
            await self.db.execute(select(HookBinding).where(HookBinding.hook_id == hook.id))
        ).scalars().all()
        for b in bindings:
            await self.db.delete(b)
        await self.db.delete(hook)

    async def list_bindings(self, hook_id: UUID) -> list[HookBindingOut]:
        await self._get_hook_or_raise(hook_id)
        rows = (
            await self.db.execute(
                select(HookBinding)
                .where(HookBinding.hook_id == hook_id, HookBinding.tenant_id == self.ctx.tenant_id)
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
        if not binding or binding.tenant_id != self.ctx.tenant_id:
            raise NotFoundError("绑定不存在")
        await self.db.delete(binding)
