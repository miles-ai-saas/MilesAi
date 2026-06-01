"""收付款管理 HTTP API，路由前缀 `/biz/payments`。

提供收付款记录的 CRUD 接口；包含 GET /financial-summary 财务概览端点，汇总收付款统计数据。
列表查询需要 contract_id 必填参数。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.payment import (
    BizPaymentCreate,
    BizPaymentOut,
    BizPaymentUpdate,
    FinancialSummaryOut,
)
from app.biz.services.payment import PaymentService
from app.common.response import ok
from app.common.schema import ApiResponse
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> PaymentService:
    return PaymentService(db, ctx)


@router.get("/financial-summary", response_model=ApiResponse[FinancialSummaryOut])
async def get_financial_summary(
    ctx: TenantContext = Depends(require_permissions("biz:payment:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取收付款财务概览，汇总应收/已收/应付/已付等统计数据。"""
    return ok(await _svc(db, ctx).financial_summary())


@router.get("/pending", response_model=ApiResponse[list[BizPaymentOut]])
async def list_pending_payments(
    ctx: TenantContext = Depends(require_permissions("biz:payment:read")),
    db: AsyncSession = Depends(get_db),
):
    """列出全部待收付记录（跨合同）。"""
    return ok(await _svc(db, ctx).list_pending_payments())


@router.get("", response_model=ApiResponse[list[BizPaymentOut]])
async def list_payments(
    contract_id: UUID = Query(...),
    ctx: TenantContext = Depends(require_permissions("biz:payment:read")),
    db: AsyncSession = Depends(get_db),
):
    """按合同查询收付款记录列表，contract_id 必填。"""
    return ok(await _svc(db, ctx).list_by_contract(contract_id))


@router.post("", response_model=ApiResponse[BizPaymentOut])
async def create_payment(
    body: BizPaymentCreate,
    ctx: TenantContext = Depends(require_permissions("biz:payment:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建收付款记录。"""
    return ok(await _svc(db, ctx).create(body))


@router.patch("/{payment_id}", response_model=ApiResponse[BizPaymentOut])
async def update_payment(
    payment_id: UUID,
    body: BizPaymentUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:payment:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新收付款记录。"""
    return ok(await _svc(db, ctx).update(payment_id, body))


@router.delete("/{payment_id}", response_model=ApiResponse[None])
async def delete_payment(
    payment_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:payment:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除收付款记录。"""
    await _svc(db, ctx).delete(payment_id)
    return ok(message="已删除")
