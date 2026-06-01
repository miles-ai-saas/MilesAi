"""业务中心全局搜索。"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.search import BizSearchHit, BizSearchOut
from app.core.service import BaseService
from app.core.soft_delete import not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.models.biz import BizClient, BizContract, BizOpportunity, BizProject


class BizSearchService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def search(self, query: str, *, limit: int = 12) -> BizSearchOut:
        q = (query or "").strip()
        if len(q) < 1:
            return BizSearchOut(query=q, items=[])
        per_kind = max(3, limit // 4)
        pattern = f"%{q}%"
        items: list[BizSearchHit] = []

        client_rows = await self.db.scalars(
            select(BizClient)
            .where(*tenant_filters(self.ctx, BizClient.tenant_id), not_deleted(BizClient), BizClient.name.ilike(pattern))
            .order_by(BizClient.updated_at.desc())
            .limit(per_kind)
        )
        for row in client_rows:
            items.append(BizSearchHit(kind="client", id=str(row.id), title=row.name, subtitle=row.short_name or "客户"))

        project_rows = await self.db.execute(
            select(BizProject, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizProject.client_id, isouter=True)
            .where(
                *tenant_filters(self.ctx, BizProject.tenant_id),
                not_deleted(BizProject),
                or_(BizProject.name.ilike(pattern), BizProject.code.ilike(pattern)),
            )
            .order_by(BizProject.updated_at.desc())
            .limit(per_kind)
        )
        for r in project_rows:
            items.append(BizSearchHit(
                kind="project",
                id=str(r.BizProject.id),
                title=r.BizProject.name,
                subtitle=r.client_name or r.BizProject.status,
            ))

        opp_rows = await self.db.execute(
            select(BizOpportunity, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizOpportunity.client_id, isouter=True)
            .where(
                *tenant_filters(self.ctx, BizOpportunity.tenant_id),
                not_deleted(BizOpportunity),
                or_(BizOpportunity.name.ilike(pattern), BizOpportunity.code.ilike(pattern)),
            )
            .order_by(BizOpportunity.updated_at.desc())
            .limit(per_kind)
        )
        for r in opp_rows:
            items.append(BizSearchHit(
                kind="opportunity",
                id=str(r.BizOpportunity.id),
                title=r.BizOpportunity.name,
                subtitle=r.client_name or r.BizOpportunity.stage,
            ))

        contract_rows = await self.db.execute(
            select(BizContract, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizContract.client_id, isouter=True)
            .where(
                *tenant_filters(self.ctx, BizContract.tenant_id),
                not_deleted(BizContract),
                or_(BizContract.name.ilike(pattern), BizContract.contract_no.ilike(pattern)),
            )
            .order_by(BizContract.updated_at.desc())
            .limit(per_kind)
        )
        for r in contract_rows:
            items.append(BizSearchHit(
                kind="contract",
                id=str(r.BizContract.id),
                title=r.name,
                subtitle=r.client_name or r.BizContract.status,
            ))

        return BizSearchOut(query=q, items=items[:limit])
