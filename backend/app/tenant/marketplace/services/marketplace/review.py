"""应用市场平台审核。"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError
from app.common.schema import PageParams, PageResult
from app.tenant.marketplace.models import MarketplaceApp, MarketplaceAppStatus
from app.tenant.marketplace.schemas.marketplace import MarketplaceAppOut


class MarketplaceReviewMixin:
    """平台侧应用审核通过/驳回。"""
    async def list_pending_apps(self, params: PageParams) -> PageResult[MarketplaceAppOut]:
        """审核队列：PENDING_REVIEW 状态应用。"""
        filters = [MarketplaceApp.status == MarketplaceAppStatus.PENDING_REVIEW]
        stmt = (
            select(MarketplaceApp)
            .where(*filters)
            .options(selectinload(MarketplaceApp.category))
            .order_by(MarketplaceApp.submitted_at.asc().nulls_last())
        )
        count_stmt = select(func.count(MarketplaceApp.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        installed_ids = await self.installed_app_ids()
        items = [
            self.app_out(
                a,
                installed=a.id in installed_ids,
                category_name=a.category.name if a.category else None,
            )
            for a in apps
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def approve_app(self, app_id: UUID) -> MarketplaceAppOut:
        """审核通过 → PUBLISHED，记录 reviewed_by/at。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PENDING_REVIEW:
            raise BadRequestError("仅待审核应用可通过")
        app.status = MarketplaceAppStatus.PUBLISHED
        app.reviewed_at = datetime.now(timezone.utc)
        app.reviewed_by = self.ctx.user_id
        app.review_note = None
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self.installed_app_ids()
        return self.app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )

    async def reject_app(self, app_id: UUID, *, note: str | None) -> MarketplaceAppOut:
        """驳回 → REJECTED，写入 review_note。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PENDING_REVIEW:
            raise BadRequestError("仅待审核应用可驳回")
        app.status = MarketplaceAppStatus.REJECTED
        app.reviewed_at = datetime.now(timezone.utc)
        app.reviewed_by = self.ctx.user_id
        app.review_note = (note or "").strip() or "未填写驳回原因"
        await self.db.flush()
        await self.db.refresh(app, ["category"])
        installed_ids = await self.installed_app_ids()
        return self.app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
        )
