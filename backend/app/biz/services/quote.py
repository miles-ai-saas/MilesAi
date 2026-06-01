"""商机报价 CRUD。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.opportunity import OpportunityRepository
from app.biz.repositories.quote import QuoteRepository
from app.biz.schemas.quote import BizQuoteCreate, BizQuoteOut, BizQuoteUpdate
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.biz import BizQuote


class QuoteService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = QuoteRepository(db)
        self.opp_repo = OpportunityRepository(db)

    async def list_quotes(self, opportunity_id: UUID) -> list[BizQuoteOut]:
        await self._get_opportunity(opportunity_id)
        rows = await self.repo.list_by_opportunity(self.ctx.tenant_id, opportunity_id)
        return [self._to_out(r) for r in rows]

    async def create(self, opportunity_id: UUID, body: BizQuoteCreate) -> BizQuoteOut:
        opp = await self._get_opportunity(opportunity_id)
        row = BizQuote(
            tenant_id=self.ctx.tenant_id,
            opportunity_id=opportunity_id,
            client_id=opp.client_id,
            name=body.name.strip(),
            amount=body.amount,
            status=body.status or "draft",
            version=body.version,
            valid_until=body.valid_until,
            remark=body.remark,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.quote.create",
            resource_type="biz_quote",
            resource_id=row.id,
            detail={"opportunity_id": str(opportunity_id), "name": row.name, "amount": row.amount},
        )
        return self._to_out(row)

    async def update(self, opportunity_id: UUID, quote_id: UUID, body: BizQuoteUpdate) -> BizQuoteOut:
        row = await self._get_or_raise(opportunity_id, quote_id)
        for f in ("name", "amount", "status", "version", "valid_until", "remark"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f == "name" else val)
        await self.db.flush()
        return self._to_out(row)

    async def delete(self, opportunity_id: UUID, quote_id: UUID) -> None:
        row = await self._get_or_raise(opportunity_id, quote_id)
        await mark_deleted(self.db, row)

    async def _get_opportunity(self, opportunity_id: UUID):
        row = await self.opp_repo.get_by_id(opportunity_id)
        if not row:
            raise NotFoundError("商机不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _get_or_raise(self, opportunity_id: UUID, quote_id: UUID) -> BizQuote:
        await self._get_opportunity(opportunity_id)
        row = await self.repo.get_by_id(quote_id)
        if not row or row.opportunity_id != opportunity_id:
            raise NotFoundError("报价不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    def _to_out(self, r: BizQuote) -> BizQuoteOut:
        valid = r.valid_until.isoformat() if hasattr(r.valid_until, "isoformat") and r.valid_until else r.valid_until
        return BizQuoteOut(
            id=r.id,
            opportunity_id=r.opportunity_id,
            client_id=r.client_id,
            name=r.name,
            amount=r.amount,
            status=r.status,
            version=r.version,
            valid_until=valid,
            remark=r.remark,
            created_by=r.created_by,
        )
