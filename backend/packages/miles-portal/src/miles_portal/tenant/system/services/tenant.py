"""租户（组织）CRUD；通常仅超管或平台管理员可跨租户列表。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.schema import PageParams, PageResult
from miles_core.models.platform.tenant import Tenant
from miles_core.service import BaseService
from miles_core.tenant import TenantContext
from miles_portal.tenant.system.repositories.tenant import TenantRepository
from miles_portal.tenant.system.schemas.tenant import TenantCreate, TenantOut, TenantUpdate


class TenantService(BaseService):
    """租户主数据；name 全局唯一由 repository.ensure_name_unique 保证。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = TenantRepository(db)

    async def list_tenants(self, params: PageParams) -> PageResult[TenantOut]:
        """分页列出全部租户（按创建时间倒序）。"""
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            order_by=Tenant.created_at.desc(),
        )
        return PageResult(
            items=[TenantOut.model_validate(t) for t in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_tenant(self, body: TenantCreate) -> TenantOut:
        """创建租户；名称重复抛 BadRequestError。"""
        await self.repo.ensure_name_unique(body.name)
        tenant = await self.repo.create(**body.model_dump())
        await self.db.refresh(tenant)
        return TenantOut.model_validate(tenant)

    async def get_tenant(self, tenant_id: UUID) -> TenantOut:
        """按 ID 获取租户，不存在抛 NotFoundError。"""
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        return TenantOut.model_validate(tenant)

    async def update_tenant(self, tenant_id: UUID, body: TenantUpdate) -> TenantOut:
        """更新租户；非超管会被剔除配额类字段，改名时校验唯一性。"""
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        data = body.model_dump(exclude_unset=True)
        if not self.ctx.is_superuser:
            for key in (
                "max_knowledge_bases",
                "max_storage_mb",
                "max_tokens_monthly",
                "max_agents",
                "max_flows",
            ):
                data.pop(key, None)
        if "name" in data:
            await self.repo.ensure_name_unique(data["name"], exclude_id=tenant_id)
        await self.repo.update_fields(tenant, data)
        await self.db.refresh(tenant)
        return TenantOut.model_validate(tenant)
