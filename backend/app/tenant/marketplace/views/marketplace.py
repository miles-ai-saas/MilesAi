"""应用市场 HTTP API：浏览、上架、审核、安装与评分。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.marketplace.schemas.meta import MarketplaceMetaOut
from app.tenant.marketplace.schemas.marketplace import (
    AppCategoryOut,
    AppInstallOut,
    AppInstallResult,
    AppRatingCreate,
    AppRatingOut,
    AppReviewBody,
    AppRollbackPreview,
    AppRollbackResult,
    AppUpgradePreview,
    AppUpgradeResult,
    MarketplaceAppCreate,
    MarketplaceAppCreateFromResources,
    MarketplaceAppDetail,
    MarketplaceAppOut,
    MarketplaceAppUpdate,
)
from app.tenant.marketplace.services.marketplace import MarketplaceService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> MarketplaceService:
    return MarketplaceService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[MarketplaceMetaOut])
async def marketplace_meta(
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("/categories", response_model=ApiResponse[list[AppCategoryOut]])
async def list_categories(
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).list_categories())


@router.get("/apps", response_model=ApiResponse[PageResult[MarketplaceAppOut]])
async def list_apps(
    category: str | None = Query(None, description="分类 slug"),
    sort: str = Query("installs", description="installs | rating"),
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_apps(params, category_slug=category, sort=sort, tag_ids=tag_ids)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/apps/mine", response_model=ApiResponse[PageResult[MarketplaceAppOut]])
async def list_my_apps(
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("marketplace:write")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_my_apps(params, tag_ids=tag_ids)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/apps/pending", response_model=ApiResponse[PageResult[MarketplaceAppOut]])
async def list_pending_apps(
    tag_ids: list[UUID] | None = Query(None, description="按标签筛选（任一匹配）"),
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("marketplace:review")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_pending_apps(params, tag_ids=tag_ids)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/apps/{app_id}", response_model=ApiResponse[MarketplaceAppDetail])
async def get_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_app(app_id))


@router.get("/apps/{app_id}/ratings", response_model=ApiResponse[PageResult[AppRatingOut]])
async def list_app_ratings(
    app_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_app_ratings(app_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/apps", response_model=ApiResponse[MarketplaceAppOut])
async def create_app(
    body: MarketplaceAppCreate,
    ctx: TenantContext = Depends(require_permissions("marketplace:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_app(body))


@router.post("/apps/from-resources", response_model=ApiResponse[MarketplaceAppOut])
async def create_app_from_resources(
    body: MarketplaceAppCreateFromResources,
    ctx: TenantContext = Depends(require_permissions("marketplace:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_app_from_resources(body))


@router.patch("/apps/{app_id}", response_model=ApiResponse[MarketplaceAppOut])
async def update_app(
    app_id: UUID,
    body: MarketplaceAppUpdate,
    ctx: TenantContext = Depends(require_permissions("marketplace:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_app(app_id, body))


@router.post("/apps/{app_id}/publish", response_model=ApiResponse[MarketplaceAppOut])
async def publish_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).publish_app(app_id))


@router.post("/apps/{app_id}/approve", response_model=ApiResponse[MarketplaceAppOut])
async def approve_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:review")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).approve_app(app_id))


@router.post("/apps/{app_id}/reject", response_model=ApiResponse[MarketplaceAppOut])
async def reject_app(
    app_id: UUID,
    body: AppReviewBody,
    ctx: TenantContext = Depends(require_permissions("marketplace:review")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).reject_app(app_id, note=body.note))


@router.post("/apps/{app_id}/ratings", response_model=ApiResponse[AppRatingOut])
async def upsert_rating(
    app_id: UUID,
    body: AppRatingCreate,
    ctx: TenantContext = Depends(require_permissions("marketplace:rate")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).upsert_rating(app_id, body))


@router.delete("/apps/{app_id}/ratings/mine", response_model=ApiResponse[None])
async def delete_my_rating(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:rate")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_my_rating(app_id)
    return ok(None)


@router.post("/apps/{app_id}/install", response_model=ApiResponse[AppInstallResult])
async def install_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).install_app(app_id))


@router.post("/apps/{app_id}/trial", response_model=ApiResponse[AppInstallResult])
async def trial_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    """沙箱试用：安装应用并标记为 24 小时试用。"""
    return ok(await _svc(db, ctx).trial_app(app_id))


@router.get("/apps/{app_id}/upgrade-preview", response_model=ApiResponse[AppUpgradePreview])
async def upgrade_preview(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    """升级前 diff 预览：对比已安装资源与市场 manifest。"""
    return ok(await _svc(db, ctx).preview_upgrade(app_id))


@router.post("/apps/{app_id}/upgrade", response_model=ApiResponse[AppUpgradeResult])
async def upgrade_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    """确认后执行应用升级，同步 KB/Flow/Agent 与 installed_version。"""
    return ok(await _svc(db, ctx).upgrade_app(app_id))


@router.get("/apps/{app_id}/rollback-preview", response_model=ApiResponse[AppRollbackPreview])
async def rollback_preview(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    """回滚前 diff 预览：对比当前资源与最近一次升级前快照。"""
    return ok(await _svc(db, ctx).preview_rollback(app_id))


@router.post("/apps/{app_id}/rollback", response_model=ApiResponse[AppRollbackResult])
async def rollback_app(
    app_id: UUID,
    ctx: TenantContext = Depends(require_permissions("marketplace:install")),
    db: AsyncSession = Depends(get_db),
):
    """回滚到最近一次升级前的资源快照。"""
    return ok(await _svc(db, ctx).rollback_app(app_id))


@router.get("/installs", response_model=ApiResponse[PageResult[AppInstallOut]])
async def list_installs(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("marketplace:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_installs(params)
    return page_ok(result.items, result.total, result.page, result.size)
