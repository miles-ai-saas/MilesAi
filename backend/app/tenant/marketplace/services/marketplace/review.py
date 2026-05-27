"""应用市场平台审核。"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.schema import PageParams, PageResult
from app.marketplace.review_config import (
    assert_tenant_can_review_app,
    is_publisher_review_scope,
    require_tenant_review_allowed,
)
from app.marketplace.review_core import approve_marketplace_app, reject_marketplace_app
from app.tenant.marketplace.models import MarketplaceApp, MarketplaceAppStatus
from app.tenant.marketplace.schemas.marketplace import MarketplaceAppOut


class MarketplaceReviewMixin:
    """平台侧应用审核通过/驳回。"""
    async def list_pending_apps(
        self, params: PageParams, *, tag_ids: list[UUID] | None = None
    ) -> PageResult[MarketplaceAppOut]:
        """审核队列：PENDING_REVIEW 状态应用。"""
        await require_tenant_review_allowed(self.db, self.ctx)

        from app.models.tag import TagEntityType
        from app.tenant.tags.services.tag import TagService

        filters = [MarketplaceApp.status == MarketplaceAppStatus.PENDING_REVIEW]
        stmt = (
            select(MarketplaceApp)
            .where(*filters)
            .options(selectinload(MarketplaceApp.category))
            .order_by(MarketplaceApp.submitted_at.asc().nulls_last())
        )
        tag_filter = TagService(self.db, self.ctx).entity_id_filter(
            TagEntityType.MARKETPLACE_APP, tag_ids or []
        )
        if tag_filter is not None:
            stmt = stmt.where(MarketplaceApp.id.in_(tag_filter))
            filters.append(MarketplaceApp.id.in_(tag_filter))
        if is_publisher_review_scope():
            stmt = stmt.where(MarketplaceApp.publisher_tenant_id == self.ctx.tenant_id)
            filters.append(MarketplaceApp.publisher_tenant_id == self.ctx.tenant_id)
        count_stmt = select(func.count(MarketplaceApp.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        installed_ids = await self.installed_app_ids()
        items = await self.apps_to_out(apps, installed_ids=installed_ids)
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def approve_app(self, app_id: UUID) -> MarketplaceAppOut:
        """审核通过 → PUBLISHED，记录 reviewed_by/at。"""
        await require_tenant_review_allowed(self.db, self.ctx)
        app = await self.get_app_or_raise(app_id)
        await assert_tenant_can_review_app(
            self.db, self.ctx, publisher_tenant_id=app.publisher_tenant_id
        )
        await approve_marketplace_app(
            self.db, app, reviewer_type="tenant", reviewer_user_id=self.ctx.user_id
        )
        await self.db.refresh(app, ["category"])
        return await self.app_out_with_tags(app)

    async def reject_app(self, app_id: UUID, *, note: str | None) -> MarketplaceAppOut:
        """驳回 → REJECTED，写入 review_note。"""
        await require_tenant_review_allowed(self.db, self.ctx)
        app = await self.get_app_or_raise(app_id)
        await assert_tenant_can_review_app(
            self.db, self.ctx, publisher_tenant_id=app.publisher_tenant_id
        )
        await reject_marketplace_app(
            self.db,
            app,
            note=note,
            reviewer_type="tenant",
            reviewer_user_id=self.ctx.user_id,
        )
        await self.db.refresh(app, ["category"])
        return await self.app_out_with_tags(app)
