from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.model_catalog import (
    ModelCatalogCreate,
    ModelCatalogOut,
    ModelCatalogUpdate,
)
from app.admin.app_ops.services.model_catalog import AdminModelCatalogService
from app.admin.app_sys.deps import AdminContext, get_platform_admin
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.core.database import get_db
from app.core.deps import get_page_params

router = APIRouter(prefix="/model-catalog")


@router.get("")
async def list_model_catalog(
    vendor: str | None = Query(None),
    publish_status: str | None = Query(None),
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminModelCatalogService(db).list_catalog(
        params, vendor=vendor, publish_status=publish_status
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("")
async def create_model_catalog(
    body: ModelCatalogCreate,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminModelCatalogService(db).create(body))


@router.get("/{model_id}")
async def get_model_catalog(
    model_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminModelCatalogService(db).get(model_id))


@router.patch("/{model_id}")
async def update_model_catalog(
    model_id: UUID,
    body: ModelCatalogUpdate,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminModelCatalogService(db).update(model_id, body))


@router.post("/{model_id}/publish")
async def publish_model_catalog(
    model_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminModelCatalogService(db).publish(model_id))


@router.post("/{model_id}/deprecate")
async def deprecate_model_catalog(
    model_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminModelCatalogService(db).deprecate(model_id))


@router.delete("/{model_id}")
async def delete_model_catalog(
    model_id: UUID,
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminModelCatalogService(db).delete(model_id)
    return ok(message="已删除")
