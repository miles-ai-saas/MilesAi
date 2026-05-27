"""运营控制台聚合统计。"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.dashboard import AdminDashboardSummaryOut
from app.admin.models import AuditLog, BillingPlan, RiskEvent, TenantBill
from app.models.tenant import Tenant, TenantStatus


class AdminDashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_summary(self) -> AdminDashboardSummaryOut:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        tenants_total = int(
            await self.db.scalar(select(func.count()).select_from(Tenant)) or 0
        )
        tenants_active = int(
            await self.db.scalar(
                select(func.count())
                .select_from(Tenant)
                .where(Tenant.status == TenantStatus.ACTIVE)
            )
            or 0
        )
        risk_open = int(
            await self.db.scalar(
                select(func.count())
                .select_from(RiskEvent)
                .where(RiskEvent.is_resolved.is_(False))
            )
            or 0
        )
        bills_total = int(
            await self.db.scalar(select(func.count()).select_from(TenantBill)) or 0
        )
        bills_issued_month = int(
            await self.db.scalar(
                select(func.count())
                .select_from(TenantBill)
                .where(TenantBill.created_at >= month_start)
            )
            or 0
        )
        audit_today = int(
            await self.db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.created_at >= today_start)
            )
            or 0
        )
        plans_active = int(
            await self.db.scalar(
                select(func.count())
                .select_from(BillingPlan)
                .where(BillingPlan.is_active.is_(True))
            )
            or 0
        )

        return AdminDashboardSummaryOut(
            tenants_total=tenants_total,
            tenants_active=tenants_active,
            risk_open=risk_open,
            bills_total=bills_total,
            bills_issued_month=bills_issued_month,
            audit_today=audit_today,
            plans_active=plans_active,
        )
