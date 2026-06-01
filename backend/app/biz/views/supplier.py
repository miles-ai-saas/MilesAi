"""供应商 HTTP API，路由前缀 `/biz/suppliers`。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.schemas.supplier import (
    BizProjectSupplierCreate,
    BizProjectSupplierOut,
    BizProjectSupplierUpdate,
    BizSupplierContactCreate,
    BizSupplierContactOut,
    BizSupplierCreate,
    BizSupplierOut,
    BizSupplierUpdate,
)
from app.biz.services.supplier import SupplierService
from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageResult
from app.core.deps import require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> SupplierService:
    return SupplierService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[BizSupplierOut]])
async def list_suppliers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("biz:supplier:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_suppliers(page=page, size=size, search=search, category=category, status=status)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[BizSupplierOut])
async def create_supplier(
    body: BizSupplierCreate,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_supplier(body))


@router.get("/{supplier_id}", response_model=ApiResponse[BizSupplierOut])
async def get_supplier(
    supplier_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_supplier(supplier_id))


@router.patch("/{supplier_id}", response_model=ApiResponse[BizSupplierOut])
async def update_supplier(
    supplier_id: UUID,
    body: BizSupplierUpdate,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_supplier(supplier_id, body))


@router.delete("/{supplier_id}", response_model=ApiResponse[None])
async def delete_supplier(
    supplier_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_supplier(supplier_id)
    return ok(message="已删除")


# ── contacts ──

@router.get("/{supplier_id}/contacts", response_model=ApiResponse[list[BizSupplierContactOut]])
async def list_contacts(
    supplier_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_contacts(supplier_id))


@router.post("/{supplier_id}/contacts", response_model=ApiResponse[BizSupplierContactOut])
async def create_contact(
    supplier_id: UUID,
    body: BizSupplierContactCreate,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_contact(supplier_id, body))


@router.patch("/{supplier_id}/contacts/{contact_id}", response_model=ApiResponse[BizSupplierContactOut])
async def update_contact(
    supplier_id: UUID,
    contact_id: UUID,
    body: BizSupplierContactCreate,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_contact(contact_id, body))


@router.delete("/{supplier_id}/contacts/{contact_id}", response_model=ApiResponse[None])
async def delete_contact(
    supplier_id: UUID,
    contact_id: UUID,
    ctx: TenantContext = Depends(require_permissions("biz:supplier:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_contact(contact_id)
    return ok(message="已删除")
