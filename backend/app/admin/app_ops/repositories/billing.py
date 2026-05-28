from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.admin.models import BillLineItem, BillingPlan, TenantBill
from app.core.repository import BaseRepository


class BillingPlanRepository(BaseRepository[BillingPlan]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BillingPlan)

    async def list_ordered(self) -> list[BillingPlan]:
        result = await self.db.execute(select(BillingPlan).order_by(BillingPlan.price_monthly))
        return list(result.scalars().all())


class TenantBillRepository(BaseRepository[TenantBill]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, TenantBill)

    async def get_with_line_items(self, bill_id: UUID) -> TenantBill | None:
        stmt = select(TenantBill).where(TenantBill.id == bill_id).options(selectinload(TenantBill.line_items))
        return (await self.db.execute(stmt)).scalar_one_or_none()


class BillLineItemRepository(BaseRepository[BillLineItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BillLineItem)
