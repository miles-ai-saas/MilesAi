from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.tenant import Tenant
from app.app_tenant.system.repositories.tenant import TenantRepository
from app.common.schema import PageParams, PageResult
from app.app_tenant.system.schemas.tenant import TenantCreate, TenantOut, TenantUpdate
from app.core.service import BaseService


class TenantService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = TenantRepository(db)

    async def list_tenants(self, params: PageParams) -> PageResult[TenantOut]:
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
        await self.repo.ensure_name_unique(body.name)
        tenant = await self.repo.create(**body.model_dump())
        await self.db.refresh(tenant)
        return TenantOut.model_validate(tenant)

    async def get_tenant(self, tenant_id: UUID) -> TenantOut:
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        return TenantOut.model_validate(tenant)

    async def update_tenant(self, tenant_id: UUID, body: TenantUpdate) -> TenantOut:
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        data = body.model_dump(exclude_unset=True)
        if "name" in data:
            await self.repo.ensure_name_unique(data["name"], exclude_id=tenant_id)
        await self.repo.update_fields(tenant, data)
        await self.db.refresh(tenant)
        return TenantOut.model_validate(tenant)
