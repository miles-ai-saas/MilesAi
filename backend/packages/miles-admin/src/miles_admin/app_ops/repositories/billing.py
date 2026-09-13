"""运营端计费仓储：套餐、账单与明细项。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_admin.models import BillingPlan, BillLineItem, TenantBill
from miles_core.repository import BaseRepository


class BillingPlanRepository(BaseRepository[BillingPlan]):
    """计费套餐仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BillingPlan)

    async def list_ordered(self) -> list[BillingPlan]:
        """按月费升序返回全部套餐。"""
        result = await self.db.execute(select(BillingPlan).order_by(BillingPlan.price_monthly))
        return list(result.scalars().all())


class TenantBillRepository(BaseRepository[TenantBill]):
    """租户账单仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, TenantBill)

    async def get_with_line_items(self, bill_id: UUID) -> TenantBill | None:
        """按 ID 加载账单并预取明细项（selectinload）。"""
        stmt = select(TenantBill).where(TenantBill.id == bill_id).options(selectinload(TenantBill.line_items))
        return (await self.db.execute(stmt)).scalar_one_or_none()


class BillLineItemRepository(BaseRepository[BillLineItem]):
    """账单明细项仓储。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BillLineItem)
