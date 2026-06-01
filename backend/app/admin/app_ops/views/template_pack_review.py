"""运营端服务线模板包审核 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.template_pack_review import AdminTemplatePackReviewService
from app.admin.app_sys.deps import AdminContext, require_admin_role
from app.common.exceptions import BadRequestError
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.core.deps import get_page_params
from app.infra.db import get_db

router = APIRouter()


class TemplatePackReviewBody(BaseModel):
    note: str | None = None


class TemplatePackOpsBody(BaseModel):
    is_featured: bool | None = None


@router.get("/template-packs/pending")
async def list_pending_template_packs(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminTemplatePackReviewService(db).list_pending(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/template-packs/published")
async def list_published_template_packs(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminTemplatePackReviewService(db).list_published(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/template-packs/{pack_id}")
async def get_template_pack_for_review(
    pack_id: UUID,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminTemplatePackReviewService(db).get_detail(pack_id))


@router.post("/template-packs/{pack_id}/approve")
async def approve_template_pack(
    pack_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    pack = await AdminTemplatePackReviewService(db).approve(pack_id, admin_id=ctx.admin_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="template_pack.approve",
        resource_type="biz_template_pack",
        resource_id=str(pack_id),
        request=request,
    )
    return ok(pack)


@router.post("/template-packs/{pack_id}/reject")
async def reject_template_pack(
    pack_id: UUID,
    body: TemplatePackReviewBody,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    pack = await AdminTemplatePackReviewService(db).reject(pack_id, admin_id=ctx.admin_id, note=body.note)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="template_pack.reject",
        resource_type="biz_template_pack",
        resource_id=str(pack_id),
        request=request,
        detail={"note": body.note},
    )
    return ok(pack)


@router.post("/template-packs/{pack_id}/unpublish")
async def unpublish_template_pack(
    pack_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    pack = await AdminTemplatePackReviewService(db).unpublish(pack_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="template_pack.unpublish",
        resource_type="biz_template_pack",
        resource_id=str(pack_id),
        request=request,
    )
    return ok(pack)


@router.patch("/template-packs/{pack_id}")
async def update_template_pack_ops(
    pack_id: UUID,
    body: TemplatePackOpsBody,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    svc = AdminTemplatePackReviewService(db)
    if body.is_featured is None:
        raise BadRequestError("请指定运营字段")
    pack = await svc.set_featured(pack_id, featured=body.is_featured)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="template_pack.feature" if body.is_featured else "template_pack.unfeature",
        resource_type="biz_template_pack",
        resource_id=str(pack_id),
        request=request,
    )
    return ok(pack)
