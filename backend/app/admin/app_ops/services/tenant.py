"""运营端租户生命周期：创建、套餐配额、用量统计与硬删（purge_tenant_data）。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.admin.app_ops.repositories.billing import BillingPlanRepository
from app.admin.app_ops.repositories.tenant import AdminTenantRepository
from app.admin.app_ops.schemas.tenant import (
    AdminTenantCreate,
    AdminTenantDetail,
    AdminTenantOut,
    AdminTenantUpdate,
    TenantQuotaUpdate,
    TenantUsageStats,
)
from app.models.tenant import Tenant, TenantStatus
from app.common.schema import PageParams, PageResult


class AdminTenantService:
    """租户 CRUD；plan_id 变更时同步 max_* 配额字段。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AdminTenantRepository(db)
        self.plans = BillingPlanRepository(db)

    async def _apply_plan(self, tenant: Tenant, plan_id: UUID | None) -> None:
        if not plan_id:
            return
        plan = await self.plans.get_by_id(plan_id)
        if not plan:
            raise NotFoundError("套餐不存在")
        if not plan.is_active:
            raise BadRequestError("该套餐已停用，不可绑定租户")
        tenant.plan_id = plan.id
        tenant.max_knowledge_bases = plan.max_knowledge_bases
        tenant.max_storage_mb = plan.max_storage_mb
        tenant.max_tokens_monthly = plan.max_tokens_monthly
        tenant.max_agents = plan.max_agents
        tenant.max_flows = plan.max_flows

    def _out(self, tenant: Tenant, plan_name: str | None = None) -> AdminTenantOut:
        return AdminTenantOut(
            id=tenant.id,
            name=tenant.name,
            description=tenant.description,
            is_active=tenant.is_active,
            status=tenant.status,
            plan_id=tenant.plan_id,
            plan_name=plan_name,
            max_knowledge_bases=tenant.max_knowledge_bases,
            max_storage_mb=tenant.max_storage_mb,
            max_tokens_monthly=int(tenant.max_tokens_monthly),
            max_agents=tenant.max_agents,
            max_flows=tenant.max_flows,
            tokens_used_month=int(tenant.tokens_used_month),
            storage_used_mb=tenant.storage_used_mb,
            created_at=tenant.created_at,
        )

    async def _plan_name(self, plan_id: UUID | None) -> str | None:
        if not plan_id:
            return None
        plan = await self.plans.get_by_id(plan_id)
        return plan.name if plan else None

    async def list_tenants(
        self,
        params: PageParams,
        *,
        status: TenantStatus | None = None,
        plan_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> PageResult[AdminTenantOut]:
        page = await self.repo.list_for_admin(params, status=status, plan_id=plan_id, is_active=is_active)
        plans = await self.repo.plan_names_by_ids({t.plan_id for t in page.items if t.plan_id})
        items = [self._out(t, plans.get(t.plan_id)) for t in page.items]
        return PageResult(items=items, total=page.total, page=page.page, size=page.size)

    async def create_tenant(self, body: AdminTenantCreate) -> AdminTenantOut:
        await self.repo.ensure_name_unique(body.name)
        tenant = await self.repo.create(
            name=body.name,
            description=body.description,
            is_active=True,
            status=body.status,
        )
        await self._apply_plan(tenant, body.plan_id)
        await self.db.flush()
        return self._out(tenant, await self._plan_name(tenant.plan_id))

    async def _usage(self, tenant_id: UUID) -> TenantUsageStats:
        counts = await self.repo.usage_counts(tenant_id)
        tenant = await self.repo.get_by_id(tenant_id)
        return TenantUsageStats(
            knowledge_bases=counts["knowledge_bases"],
            documents=counts["documents"],
            agents=counts["agents"],
            flows=counts["flows"],
            users=counts["users"],
            storage_used_mb=counts["storage_used_mb"],
            tokens_used_month=int(tenant.tokens_used_month) if tenant else 0,
        )

    async def get_tenant_usage(self, tenant_id: UUID) -> TenantUsageStats:
        await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        return await self._usage(tenant_id)

    async def get_tenant_detail(self, tenant_id: UUID) -> AdminTenantDetail:
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        usage = await self._usage(tenant_id)
        tenant.storage_used_mb = usage.storage_used_mb
        await self.db.flush()
        base = self._out(tenant, await self._plan_name(tenant.plan_id))
        return AdminTenantDetail(**base.model_dump(), usage=usage)

    async def update_tenant(self, tenant_id: UUID, body: AdminTenantUpdate) -> AdminTenantOut:
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        data = body.model_dump(exclude_unset=True)
        plan_id = data.pop("plan_id", None)
        if "name" in data:
            await self.repo.ensure_name_unique(data["name"], exclude_id=tenant_id)
        await self.repo.update_fields(tenant, data)
        if plan_id is not None:
            await self._apply_plan(tenant, plan_id)
        await self.db.flush()
        return self._out(tenant, await self._plan_name(tenant.plan_id))

    async def update_quota(self, tenant_id: UUID, body: TenantQuotaUpdate) -> AdminTenantOut:
        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        await self.repo.update_fields(tenant, body.model_dump(exclude_unset=True))
        await self.db.flush()
        return self._out(tenant)

    async def delete_tenant(self, tenant_id: UUID) -> None:
        """删除租户：purge_tenant_data 硬删业务数据+OSS，再删 tenants（adm 账单/风控可保留）。"""
        from app.deletion.tenant import purge_tenant_data

        tenant = await self.repo.get_by_id_or_raise(tenant_id, label="租户不存在")
        await purge_tenant_data(self.db, tenant_id)
        await self.db.delete(tenant)
        await self.db.flush()
