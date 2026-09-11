"""钩子定义与绑定 CRUD（执行由 HookRunner / HookExecutor 负责）。

创建钩子时默认附带一条 HookBinding（scope/trigger 来自请求体）。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.hooks.meta import hook_meta_dict
from miles_portal.tenant.hooks.models import HookBinding, HookDefinition, HookExecutionLog
from miles_portal.tenant.hooks.schemas.meta import HookMetaOut
from miles_portal.tenant.hooks.schemas.execution import HookExecutionLogOut
from miles_portal.tenant.hooks.schemas.hook import (
    HookBindingCreate,
    HookBindingOut,
    HookDefinitionCreate,
    HookDefinitionOut,
    HookDefinitionUpdate,
)
from miles_common.schema import PageParams, PageResult
from miles_common.exceptions import NotFoundError
from miles_core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, mark_deleted_where, not_deleted
from miles_core.service import BaseService


class HookService(BaseService):
    """租户钩子配置管理。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _get_hook_or_raise(self, hook_id: UUID) -> HookDefinition:
        """加载 HookDefinition 并校验租户。"""
        hook = await self.db.get(HookDefinition, hook_id)
        if not hook or is_marked_deleted(hook):
            raise NotFoundError("钩子不存在")
        assert_tenant_access(self.ctx, hook.tenant_id)
        return hook

    async def get_meta(self) -> HookMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return HookMetaOut.model_validate(hook_meta_dict())

    async def list_hooks(self, params: PageParams) -> PageResult[HookDefinitionOut]:
        """分页列出当前租户钩子定义，按创建时间倒序。"""
        filters = append_not_deleted(tenant_filters(self.ctx, HookDefinition.tenant_id), HookDefinition)
        total = await self.db.scalar(select(func.count()).select_from(HookDefinition).where(*filters))
        stmt = select(HookDefinition).where(*filters).order_by(HookDefinition.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[HookDefinitionOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_hook(self, body: HookDefinitionCreate) -> HookDefinitionOut:
        """创建钩子定义，并附带一条 scope/trigger 来自请求体的初始绑定。"""
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
        """仅更新显式传入的字段（``exclude_unset``）。"""
        hook = await self._get_hook_or_raise(hook_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(hook, k, v)
        await self.db.flush()
        await self.db.refresh(hook)
        return HookDefinitionOut.model_validate(hook)

    async def delete_hook(self, hook_id: UUID) -> None:
        """软删钩子定义及其全部绑定。"""
        hook = await self._get_hook_or_raise(hook_id)
        await mark_deleted_where(
            self.db,
            HookBinding,
            HookBinding.hook_id == hook.id,
            HookBinding.tenant_id == self.ctx.tenant_id,
        )
        await mark_deleted(self.db, hook)

    async def list_bindings(self, hook_id: UUID) -> list[HookBindingOut]:
        """列出指定钩子的有效绑定，按 priority 升序。"""
        await self._get_hook_or_raise(hook_id)
        rows = (
            (
                await self.db.execute(
                    select(HookBinding)
                    .where(
                        HookBinding.hook_id == hook_id,
                        HookBinding.tenant_id == self.ctx.tenant_id,
                        not_deleted(HookBinding),
                    )
                    .order_by(HookBinding.priority.asc())
                )
            )
            .scalars()
            .all()
        )
        return [HookBindingOut.model_validate(b) for b in rows]

    async def create_binding(self, hook_id: UUID, body: HookBindingCreate) -> HookBindingOut:
        """为指定钩子新增绑定。"""
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
        """软删绑定；不存在、已删或跨租户时抛 ``NotFoundError``。"""
        binding = await self.db.get(HookBinding, binding_id)
        if not binding or binding.tenant_id != self.ctx.tenant_id or is_marked_deleted(binding):
            raise NotFoundError("绑定不存在")
        await mark_deleted(self.db, binding)

    async def list_executions(
        self,
        params: PageParams,
        *,
        hook_id: UUID | None = None,
    ) -> PageResult[HookExecutionLogOut]:
        """分页查询执行日志，可按 hook_id 过滤；指定时先校验钩子归属。"""
        if hook_id:
            await self._get_hook_or_raise(hook_id)
        filters = append_not_deleted(
            tenant_filters(self.ctx, HookExecutionLog.tenant_id),
            HookExecutionLog,
        )
        if hook_id:
            filters.append(HookExecutionLog.hook_id == hook_id)
        total = await self.db.scalar(select(func.count()).select_from(HookExecutionLog).where(*filters))
        stmt = select(HookExecutionLog).where(*filters).order_by(HookExecutionLog.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[HookExecutionLogOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )
