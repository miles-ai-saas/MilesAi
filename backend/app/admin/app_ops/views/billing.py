"""运营端计费套餐与租户账单 HTTP API。"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import BillStatus
from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.billing import AdminBillingService
from app.admin.app_ops.schemas import BillingPlanCreate, BillingPlanUpdate, TenantBillStatusUpdate
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
from app.core.deps import get_page_params

router = APIRouter()


@router.get("/billing/plans")
async def list_plans(ctx: AdminContext = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    return ok(await AdminBillingService(db).list_plans())


@router.post("/billing/plans")
async def create_plan(
    body: BillingPlanCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("billing")),
    db: AsyncSession = Depends(get_db),
):
    plan = await AdminBillingService(db).create_plan(body)
    await write_audit_log(db, admin_id=ctx.admin_id, action="plan.create", request=request)
    return ok(plan)


@router.patch("/billing/plans/{plan_id}")
async def update_plan(
    plan_id: UUID,
    body: BillingPlanUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("billing")),
    db: AsyncSession = Depends(get_db),
):
    plan = await AdminBillingService(db).update_plan(plan_id, body)
    await write_audit_log(db, admin_id=ctx.admin_id, action="plan.update", request=request)
    return ok(plan)


@router.get("/billing/bills")
async def list_bills(
    tenant_id: UUID | None = None,
    status: BillStatus | None = None,
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminBillingService(db).list_bills(params, tenant_id=tenant_id, status=status)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/billing/bills/{bill_id}")
async def get_bill(bill_id: UUID, ctx: AdminContext = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    return ok(await AdminBillingService(db).get_bill(bill_id))


@router.post("/billing/bills/generate")
async def generate_bill(
    tenant_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    request: Request = None,
    ctx: AdminContext = Depends(require_admin_role("billing")),
    db: AsyncSession = Depends(get_db),
):
    bill = await AdminBillingService(db).generate_bill(tenant_id, period_start, period_end)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="bill.generate",
        tenant_id=tenant_id,
        request=request,
    )
    return ok(bill)


@router.patch("/billing/bills/{bill_id}")
async def update_bill_status(
    bill_id: UUID,
    body: TenantBillStatusUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("billing")),
    db: AsyncSession = Depends(get_db),
):
    bill = await AdminBillingService(db).update_bill_status(bill_id, body)
    action = "bill.paid" if body.status.value == "paid" else "bill.void"
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action=action,
        tenant_id=bill.tenant_id,
        request=request,
    )
    return ok(bill)
