"""运营端计费：套餐定义与租户账单生成/查询。"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError, BadRequestError
from app.admin.app_ops.repositories.billing import BillingPlanRepository, TenantBillRepository
from app.admin.app_ops.repositories.tenant import AdminTenantRepository
from app.admin.models import BillLineItem, BillStatus, TenantBill
from app.admin.app_ops.schemas.billing import (
    BillLineItemOut,
    BillingPlanCreate,
    BillingPlanOut,
    BillingPlanUpdate,
    TenantBillDetail,
    TenantBillOut,
    TenantBillStatusUpdate,
)
from app.common.schema import PageParams, PageResult


class AdminBillingService:
    """套餐 CRUD 与按月生成租户账单。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.plans = BillingPlanRepository(db)
        self.bills = TenantBillRepository(db)
        self.tenants = AdminTenantRepository(db)

    async def list_plans(self) -> list[BillingPlanOut]:
        """按价格升序列出套餐。"""
        rows = await self.plans.list_ordered()
        return [BillingPlanOut.model_validate(p) for p in rows]

    async def get_plan(self, plan_id: UUID) -> BillingPlanOut:
        """按 ID 取套餐，不存在抛 ``NotFoundError``。"""
        plan = await self.plans.get_by_id_or_raise(plan_id, label="套餐不存在")
        return BillingPlanOut.model_validate(plan)

    async def create_plan(self, body: BillingPlanCreate) -> BillingPlanOut:
        """创建套餐。"""
        plan = await self.plans.create(**body.model_dump())
        await self.db.refresh(plan)
        return BillingPlanOut.model_validate(plan)

    async def update_plan(self, plan_id: UUID, body: BillingPlanUpdate) -> BillingPlanOut:
        """按需更新套餐字段。"""
        plan = await self.plans.get_by_id_or_raise(plan_id, label="套餐不存在")
        plan = await self.plans.update_fields(plan, body.model_dump(exclude_unset=True))
        return BillingPlanOut.model_validate(plan)

    async def list_bills(
        self,
        params: PageParams,
        *,
        tenant_id: UUID | None = None,
        status: BillStatus | None = None,
    ) -> PageResult[TenantBillOut]:
        """分页查询账单，可按租户/状态筛选并补全租户名。"""
        filters = []
        if tenant_id:
            filters.append(TenantBill.tenant_id == tenant_id)
        if status:
            filters.append(TenantBill.status == status)
        page = await self.bills.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=TenantBill.created_at.desc(),
        )
        tenant_names = await self.tenants.tenant_names_by_ids({b.tenant_id for b in page.items})
        items = [
            TenantBillOut(
                id=b.id,
                tenant_id=b.tenant_id,
                tenant_name=tenant_names.get(b.tenant_id),
                plan_id=b.plan_id,
                period_start=b.period_start,
                period_end=b.period_end,
                amount=b.amount,
                status=b.status,
                tokens_used=int(b.tokens_used),
                storage_used_mb=b.storage_used_mb,
                created_at=b.created_at,
            )
            for b in page.items
        ]
        return PageResult(items=items, total=page.total, page=page.page, size=page.size)

    async def get_bill(self, bill_id: UUID) -> TenantBillDetail:
        """取账单详情（含明细与租户名），不存在抛 ``NotFoundError``。"""
        bill = await self.bills.get_with_line_items(bill_id)
        if not bill:
            raise NotFoundError("账单不存在")
        tenant = await self.tenants.get_by_id(bill.tenant_id)
        base = TenantBillOut(
            id=bill.id,
            tenant_id=bill.tenant_id,
            tenant_name=tenant.name if tenant else None,
            plan_id=bill.plan_id,
            period_start=bill.period_start,
            period_end=bill.period_end,
            amount=bill.amount,
            status=bill.status,
            tokens_used=int(bill.tokens_used),
            storage_used_mb=bill.storage_used_mb,
            created_at=bill.created_at,
        )
        return TenantBillDetail(
            **base.model_dump(),
            line_items=[BillLineItemOut.model_validate(i) for i in bill.line_items],
        )

    async def generate_bill(self, tenant_id: UUID, period_start: date, period_end: date) -> TenantBillDetail:
        """按账期生成账单：套餐月费 + Token/存储超量费，写入明细后返回详情。"""
        tenant = await self.tenants.get_by_id_or_raise(tenant_id, label="租户不存在")
        plan = await self.plans.get_by_id(tenant.plan_id) if tenant.plan_id else None
        base_price = plan.price_monthly if plan else Decimal("0")
        token_overage = max(0, int(tenant.tokens_used_month) - int(tenant.max_tokens_monthly))
        storage_overage = max(0, tenant.storage_used_mb - tenant.max_storage_mb)
        token_fee = Decimal(token_overage) / 1000 * Decimal("0.01")
        storage_fee = Decimal(storage_overage) * Decimal("0.1")
        amount = base_price + token_fee + storage_fee

        bill = await self.bills.create(
            tenant_id=tenant_id,
            plan_id=tenant.plan_id,
            period_start=period_start,
            period_end=period_end,
            amount=amount,
            status=BillStatus.ISSUED,
            tokens_used=int(tenant.tokens_used_month),
            storage_used_mb=tenant.storage_used_mb,
        )
        items = [
            BillLineItem(
                bill_id=bill.id,
                item_type="subscription",
                description=f"套餐 {plan.name if plan else '默认'}",
                quantity=1,
                unit_price=base_price,
                amount=base_price,
            ),
        ]
        if token_fee > 0:
            items.append(
                BillLineItem(
                    bill_id=bill.id,
                    item_type="token_overage",
                    description="Token 超量",
                    quantity=token_overage,
                    unit_price=Decimal("0.01"),
                    amount=token_fee,
                )
            )
        if storage_fee > 0:
            items.append(
                BillLineItem(
                    bill_id=bill.id,
                    item_type="storage_overage",
                    description="存储超量 (MB)",
                    quantity=storage_overage,
                    unit_price=Decimal("0.1"),
                    amount=storage_fee,
                )
            )
        for item in items:
            self.db.add(item)
        await self.db.flush()
        return await self.get_bill(bill.id)

    async def update_bill_status(self, bill_id: UUID, body: TenantBillStatusUpdate) -> TenantBillDetail:
        """将账单标记为 paid/void；仅 issued/draft 状态允许变更。"""
        if body.status not in (BillStatus.PAID, BillStatus.VOID):
            raise BadRequestError("仅支持标记为 paid 或 void")
        bill = await self.bills.get_by_id_or_raise(bill_id, label="账单不存在")
        if bill.status not in (BillStatus.ISSUED, BillStatus.DRAFT):
            raise BadRequestError("当前状态不可变更")
        bill.status = body.status
        await self.db.flush()
        return await self.get_bill(bill_id)
