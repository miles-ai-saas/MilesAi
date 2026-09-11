"""运营端租户仓储：分页查询与资源计数。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.admin.models import BillingPlan
from app.tenant.system.repositories.tenant import TenantRepository
from app.common.schema import PageParams, PageResult
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.kb import Document, KnowledgeBase
from app.models.platform.tenant import Tenant, TenantStatus
from app.models.platform.user import User


class AdminTenantRepository(TenantRepository):
    """运营侧租户查询与统计。"""

    async def list_for_admin(
        self,
        params: PageParams,
        *,
        status: TenantStatus | None = None,
        plan_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> PageResult:
        """按状态/套餐/启停筛选分页返回租户，并预取用户列表。"""
        filters = []
        if status:
            filters.append(Tenant.status == status)
        if plan_id:
            filters.append(Tenant.plan_id == plan_id)
        if is_active is not None:
            filters.append(Tenant.is_active == is_active)
        return await self.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=Tenant.created_at.desc(),
            options=[selectinload(Tenant.users)],
        )

    async def plan_names_by_ids(self, plan_ids: set[UUID]) -> dict[UUID, str]:
        """批量查询套餐 ID → 名称映射。"""
        if not plan_ids:
            return {}
        rows = (await self.db.execute(select(BillingPlan).where(BillingPlan.id.in_(plan_ids)))).scalars().all()
        return {p.id: p.name for p in rows}

    async def tenant_names_by_ids(self, tenant_ids: set[UUID]) -> dict[UUID, str]:
        """批量查询租户 ID → 名称映射。"""
        if not tenant_ids:
            return {}
        rows = (await self.db.execute(select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids)))).all()
        return {r[0]: r[1] for r in rows}

    async def usage_counts(self, tenant_id: UUID) -> dict[str, int]:
        """统计租户各资源用量（知识库/文档/智能体/工作流/用户/存储）。"""
        kbs = await self.db.scalar(select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id))
        docs = await self.db.scalar(select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id))
        agents = await self.db.scalar(select(func.count()).select_from(Agent).where(Agent.tenant_id == tenant_id))
        flows = await self.db.scalar(select(func.count()).select_from(Flow).where(Flow.tenant_id == tenant_id))
        users = await self.db.scalar(select(func.count()).select_from(User).where(User.tenant_id == tenant_id))
        storage_bytes = await self.db.scalar(select(func.coalesce(func.sum(Document.file_size), 0)).where(Document.tenant_id == tenant_id))
        return {
            "knowledge_bases": kbs or 0,
            "documents": docs or 0,
            "agents": agents or 0,
            "flows": flows or 0,
            "users": users or 0,
            "storage_used_mb": int((storage_bytes or 0) / 1024 / 1024),
        }
