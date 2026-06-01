"""收付款仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizPayment


class PaymentRepository(BaseRepository[BizPayment]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizPayment)

    async def list_by_contract(self, tenant_id: UUID, contract_id: UUID) -> list[BizPayment]:
        stmt = (
            select(BizPayment)
            .where(
                BizPayment.tenant_id == tenant_id,
                BizPayment.contract_id == contract_id,
                not_deleted(BizPayment),
            )
            .order_by(BizPayment.planned_date.asc().nulls_last(), BizPayment.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def list_pending(self, tenant_id: UUID, *, limit: int = 50) -> list[BizPayment]:
        stmt = (
            select(BizPayment)
            .where(
                BizPayment.tenant_id == tenant_id,
                BizPayment.status == "pending",
                not_deleted(BizPayment),
            )
            .order_by(BizPayment.planned_date.asc().nulls_last(), BizPayment.name.asc())
            .limit(limit)
        )
        return (await self.db.execute(stmt)).scalars().all()
