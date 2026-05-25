"""运营端应用市场分类 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.marketplace_category import (
    MarketplaceCategoryCreate,
    MarketplaceCategoryOut,
    MarketplaceCategoryUpdate,
)
from app.admin.app_ops.services.marketplace_category import AdminMarketplaceCategoryService
from app.admin.app_sys.deps import AdminContext, get_platform_admin
from app.common.response import ok
from app.common.schema import ApiResponse
from app.infra.db import get_db

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
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminMarketplaceCategoryService(db).create(body))


@router.patch("/{category_id}", response_model=ApiResponse[MarketplaceCategoryOut])
async def update_marketplace_category(
    category_id: UUID,
    body: MarketplaceCategoryUpdate,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminMarketplaceCategoryService(db).update(category_id, body))


@router.delete("/{category_id}", response_model=ApiResponse[None])
async def delete_marketplace_category(
    category_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminMarketplaceCategoryService(db).delete(category_id)
    return ok(message="已删除")
