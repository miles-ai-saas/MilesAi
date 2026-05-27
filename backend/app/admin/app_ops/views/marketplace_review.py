"""运营端应用市场审核 HTTP API（review_mode=platform）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.services.audit import write_audit_log
from app.admin.app_ops.services.marketplace_review import AdminMarketplaceReviewService
from app.admin.app_sys.deps import AdminContext, get_platform_admin, require_admin_role
from app.common.response import ok, page_ok
from app.common.schema import PageParams
from app.core.deps import get_page_params
from app.infra.db import get_db
from app.tenant.marketplace.schemas.marketplace import AppReviewBody

router = APIRouter()


@router.get("/marketplace/apps/pending")
async def list_pending_marketplace_apps(
    params: PageParams = Depends(get_page_params),
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    result = await AdminMarketplaceReviewService(db).list_pending(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/marketplace/apps/{app_id}")
async def get_marketplace_app_for_review(
    app_id: UUID,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await AdminMarketplaceReviewService(db).get_app_detail(app_id))


@router.post("/marketplace/apps/{app_id}/approve")
async def approve_marketplace_app(
    app_id: UUID,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    app = await AdminMarketplaceReviewService(db).approve(app_id, admin_id=ctx.admin_id)
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="marketplace.approve",
        resource_type="marketplace_app",
        resource_id=str(app_id),
        request=request,
    )
    return ok(app)


@router.post("/marketplace/apps/{app_id}/reject")
async def reject_marketplace_app(
    app_id: UUID,
    body: AppReviewBody,
    request: Request,
    ctx: AdminContext = Depends(require_admin_role("ops")),
    db: AsyncSession = Depends(get_db),
):
    app = await AdminMarketplaceReviewService(db).reject(
        app_id, admin_id=ctx.admin_id, note=body.note
    )
    await write_audit_log(
        db,
        admin_id=ctx.admin_id,
        action="marketplace.reject",
        resource_type="marketplace_app",
        resource_id=str(app_id),
        request=request,
        detail={"note": body.note},
    )
    return ok(app)


@router.get("/marketplace/review-mode")
async def marketplace_review_mode(
    ctx: AdminContext = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.marketplace.review_config import get_marketplace_review_mode

    return ok({"review_mode": await get_marketplace_review_mode(db)})
