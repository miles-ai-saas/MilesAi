from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, tenant_filters
from app.app_tenant.hooks.models import HookBinding, HookDefinition
from app.app_tenant.hooks.schemas.hook import HookDefinitionCreate, HookDefinitionOut
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService


class HookService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

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
