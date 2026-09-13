"""运营端应用市场审核（review_mode=platform）。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_common.exceptions import NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.marketplace import MarketplaceApp, MarketplaceAppStatus
from miles_core.models.marketplace.dto import MarketplaceAppDetail, MarketplaceAppOut
from miles_portal.marketplace.review_config import require_platform_review_allowed
from miles_portal.marketplace.review_core import approve_marketplace_app, reject_marketplace_app


class AdminMarketplaceReviewService:
    """平台审核模式下的应用审核；操作前校验当前是否允许平台审核。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _app_out(self, app: MarketplaceApp) -> MarketplaceAppOut:
        return MarketplaceAppOut(
            id=app.id,
            name=app.name,
            description=app.description,
            icon=app.icon,
            version=app.version,
            status=app.status,
            is_official=app.is_official,
            install_count=app.install_count,
            rating_avg=round(float(app.rating_avg or 0), 2),
            rating_count=int(app.rating_count or 0),
            visibility=app.visibility,
            category_id=app.category_id,
            category_name=app.category.name if app.category else None,
            tags=[],
            installed=False,
            review_note=app.review_note,
            submitted_at=app.submitted_at,
            reviewed_at=app.reviewed_at,
            created_at=app.created_at,
        )

    async def _get_app_or_raise(self, app_id: UUID) -> MarketplaceApp:
        app = await self.db.scalar(select(MarketplaceApp).where(MarketplaceApp.id == app_id).options(selectinload(MarketplaceApp.category)))
        if not app:
            raise NotFoundError("应用不存在")
        return app

    async def list_pending(self, params: PageParams) -> PageResult[MarketplaceAppOut]:
        """分页列出待审核应用（按提交时间升序，未提交排末尾）。"""
        await require_platform_review_allowed(self.db)
        filters = [MarketplaceApp.status == MarketplaceAppStatus.PENDING_REVIEW]
        total = await self.db.scalar(select(func.count(MarketplaceApp.id)).where(*filters))
        stmt = (
            select(MarketplaceApp)
            .where(*filters)
            .options(selectinload(MarketplaceApp.category))
            .order_by(MarketplaceApp.submitted_at.asc().nulls_last())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        apps = list((await self.db.execute(stmt)).scalars().all())
        return PageResult(
            items=[self._app_out(a) for a in apps],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def get_app_detail(self, app_id: UUID) -> MarketplaceAppDetail:
        """取应用详情（含 manifest），不存在抛 ``NotFoundError``。"""
        await require_platform_review_allowed(self.db)
        app = await self._get_app_or_raise(app_id)
        base = self._app_out(app)
        return MarketplaceAppDetail(**base.model_dump(), manifest=app.manifest or {})

    async def approve(self, app_id: UUID, *, admin_id: UUID) -> MarketplaceAppOut:
        """审核通过应用，并刷新分类信息后返回。"""
        await require_platform_review_allowed(self.db)
        app = await self._get_app_or_raise(app_id)
        await approve_marketplace_app(self.db, app, reviewer_type="admin", reviewer_admin_id=admin_id)
        await self.db.refresh(app, ["category"])
        return self._app_out(app)

    async def reject(self, app_id: UUID, *, admin_id: UUID, note: str | None) -> MarketplaceAppOut:
        """审核拒绝应用（可附备注），并刷新分类信息后返回。"""
        await require_platform_review_allowed(self.db)
        app = await self._get_app_or_raise(app_id)
        await reject_marketplace_app(
            self.db,
            app,
            note=note,
            reviewer_type="admin",
            reviewer_admin_id=admin_id,
        )
        await self.db.refresh(app, ["category"])
        return self._app_out(app)
