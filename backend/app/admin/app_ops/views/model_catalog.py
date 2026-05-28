"""运营端内置模型目录 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.model_catalog import (
    ModelCatalogCreate,
    ModelCatalogOut,
    ModelCatalogUpdate,
)
from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.model_catalog import AdminModelCatalogService
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.infra.db import get_db
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
    result = await AdminModelCatalogService(db).list_catalog(params, vendor=vendor, publish_status=publish_status)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("")
async def create_model_catalog(
    body: ModelCatalogCreate,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    model = await AdminModelCatalogService(db).create(body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="model.create",
        resource_type="model_catalog",
        resource_id=str(model.id),
        request=request,
        detail={"model_code": model.model_code, "name": model.name},
    )
    return ok(model)


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
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    model = await AdminModelCatalogService(db).update(model_id, body)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="model.update",
        resource_type="model_catalog",
        resource_id=str(model_id),
        request=request,
        detail=body.model_dump(mode="json", exclude_unset=True),
    )
    return ok(model)


@router.post("/{model_id}/publish")
async def publish_model_catalog(
    model_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    model = await AdminModelCatalogService(db).publish(model_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="model.publish",
        resource_type="model_catalog",
        resource_id=str(model_id),
        request=request,
    )
    return ok(model)


@router.post("/{model_id}/deprecate")
async def deprecate_model_catalog(
    model_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    model = await AdminModelCatalogService(db).deprecate(model_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="model.deprecate",
        resource_type="model_catalog",
        resource_id=str(model_id),
        request=request,
    )
    return ok(model)


@router.delete("/{model_id}")
async def delete_model_catalog(
    model_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    await AdminModelCatalogService(db).delete(model_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="model.delete",
        resource_type="model_catalog",
        resource_id=str(model_id),
        request=request,
    )
    return ok(message="已删除")
