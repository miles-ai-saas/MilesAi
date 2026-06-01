"""收付款 CRUD + 财务概览服务。

每条收付款记录绑定一个合同和项目，direction 区分收/付。
status 流：pending → paid / cancelled
财务概览从 biz_payments + biz_contracts 聚合四项统计指标。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.payment import PaymentRepository
from app.biz.schemas.payment import (
    BizPaymentCreate,
    BizPaymentOut,
    BizPaymentUpdate,
    FinancialSummaryOut,
)
from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizContract, BizPayment


class PaymentService(BaseService):
    """收付款管理——支持按合同维度查询、财务概览聚合。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = PaymentRepository(db)

    async def list_by_contract(self, contract_id: UUID) -> list[BizPaymentOut]:
        """按合同查询收付款记录（按计划日期升序）。"""
        rows = await self.repo.list_by_contract(self.ctx.tenant_id, contract_id)
        return [self._to_out(r) for r in rows]

    async def list_payments(
        self,
        *,
        contract_id: UUID | None = None,
        direction: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[BizPaymentOut]:
        """跨合同查询收付款台账，支持方向/状态筛选。"""
        rows = await self.repo.list_all(
            self.ctx.tenant_id,
            contract_id=contract_id,
            direction=direction,
            status=status,
            limit=limit,
        )
        return [self._to_out(r) for r in rows]

    async def create(self, body: BizPaymentCreate) -> BizPaymentOut:
        """创建收付款记录，direction 区分收款(in)和付款(out)。"""
        row = BizPayment(
            tenant_id=self.ctx.tenant_id,
            contract_id=body.contract_id,
            project_id=body.project_id,
            name=body.name.strip(),
            direction=body.direction,
            amount=body.amount,
            planned_date=body.planned_date,
            method=body.method,
            remark=body.remark,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def update(self, payment_id: UUID, body: BizPaymentUpdate) -> BizPaymentOut:
        """编辑收付款，可将状态改为 paid 并记录实付日期。"""
        row = await self._get_or_raise(payment_id)
        for f in ("name", "direction", "amount", "planned_date", "paid_date", "method", "status", "remark"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "remark") else val)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def delete(self, payment_id: UUID) -> None:
        """软删除收付款记录（仅标记 deleted_at）。"""
        row = await self._get_or_raise(payment_id)
        await mark_deleted(self.db, row)

    async def list_pending_payments(self, *, limit: int = 50) -> list[BizPaymentOut]:
        """跨合同列出待收付记录，按计划日期排序。"""
        rows = await self.repo.list_pending(self.ctx.tenant_id, limit=limit)
        return [self._to_out(r) for r in rows]

    async def financial_summary(self) -> FinancialSummaryOut:
        """财务概览聚合统计：
        - total_income: 所有收付款总额
        - total_paid: 已结清金额
        - total_pending_in: 待收款（direction=in 且 status=pending）
        - total_pending_out: 待付款（direction=out 且 status=pending）
        - contract_count: 合同总数
        """
        pay_filters = tenant_filters(self.ctx, BizPayment.tenant_id) + [not_deleted(BizPayment)]
        stmt = select(
            func.coalesce(func.sum(BizPayment.amount), 0),
            func.coalesce(func.sum(BizPayment.amount).filter(BizPayment.status == "paid"), 0),
            func.coalesce(func.sum(BizPayment.amount).filter(BizPayment.direction == "in", BizPayment.status == "pending"), 0),
            func.coalesce(func.sum(BizPayment.amount).filter(BizPayment.direction == "out", BizPayment.status == "pending"), 0),
        ).where(*pay_filters)
        total, paid, pending_in, pending_out = (await self.db.execute(stmt)).one()

        ctr_filters = tenant_filters(self.ctx, BizContract.tenant_id) + [not_deleted(BizContract)]
        contract_count = await self.db.scalar(select(func.count()).where(*ctr_filters)) or 0

        return FinancialSummaryOut(
            total_income=float(total), total_paid=float(paid),
            total_pending_in=float(pending_in), total_pending_out=float(pending_out),
            contract_count=contract_count,
        )

    def _to_out(self, row: BizPayment) -> BizPaymentOut:
        return BizPaymentOut(
            id=row.id, contract_id=row.contract_id, project_id=row.project_id,
            name=row.name, direction=row.direction, amount=row.amount,
            status=row.status, planned_date=row.planned_date,
            paid_date=row.paid_date, method=row.method, remark=row.remark,
        )

    async def _get_or_raise(self, payment_id: UUID) -> BizPayment:
        row = await self.repo.get_by_id(payment_id)
        if not row:
            raise NotFoundError("收付款记录不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
