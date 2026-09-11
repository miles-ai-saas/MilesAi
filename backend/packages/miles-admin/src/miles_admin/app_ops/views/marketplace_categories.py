"""运营端应用市场分类 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.schemas.marketplace_category import (
    MarketplaceCategoryCreate,
    MarketplaceCategoryOut,
    MarketplaceCategoryUpdate,
)
from miles_admin.app_ops.services.audit import write_audit_log
from miles_admin.app_ops.services.marketplace_category import AdminMarketplaceCategoryService
from miles_admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from miles_common.response import ok
from miles_common.schema import ApiResponse
from miles_core.infra.db import get_db

router = APIRouter(prefix="/marketplace-categories")


@router.get("", response_model=ApiResponse[list[MarketplaceCategoryOut]])
async def list_marketplace_categories(
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminMarketplaceCategoryService(db).list_categories())


@router.post("", response_model=ApiResponse[MarketplaceCategoryOut])
async def create_marketplace_category(
    body: MarketplaceCategoryCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminMarketplaceCategoryService(db).create(body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="marketplace_category.create",
        resource_type="marketplace_category",
        resource_id=str(row.id),
        request=request,
        detail={"name": row.name},
    )
    return ok(row)


@router.patch("/{category_id}", response_model=ApiResponse[MarketplaceCategoryOut])
async def update_marketplace_category(
    category_id: UUID,
    body: MarketplaceCategoryUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    row = await AdminMarketplaceCategoryService(db).update(category_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="marketplace_category.update",
        resource_type="marketplace_category",
        resource_id=str(category_id),
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(row)


@router.delete("/{category_id}", response_model=ApiResponse[None])
async def delete_marketplace_category(
    category_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    await AdminMarketplaceCategoryService(db).delete(category_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="marketplace_category.delete",
        resource_type="marketplace_category",
        resource_id=str(category_id),
        request=request,
    )
    return ok(message="已删除")
