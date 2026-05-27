"""应用评分。"""

from uuid import UUID

from sqlalchemy import func, select

from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import mark_deleted, not_deleted
from app.tenant.marketplace.models import AppRating, MarketplaceAppStatus
from app.tenant.marketplace.schemas.marketplace import AppRatingCreate, AppRatingOut


class MarketplaceRatingsMixin:
    """应用评分与均分统计。"""

    async def refresh_rating_stats(self, app_id: UUID) -> None:
        """重算应用 ``rating_avg`` / ``rating_count``。"""
        stmt = select(
            func.avg(AppRating.score),
            func.count(AppRating.id),
        ).where(AppRating.app_id == app_id, not_deleted(AppRating))
        avg_score, count = (await self.db.execute(stmt)).one()
        app = await self.get_app_or_raise(app_id)
        app.rating_avg = round(float(avg_score or 0), 2)
        app.rating_count = int(count or 0)
        await self.db.flush()

    async def list_app_ratings(
        self, app_id: UUID, params: PageParams
    ) -> PageResult[AppRatingOut]:
        """分页列出应用评分。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise NotFoundError("应用未上架")
        filters = [AppRating.app_id == app_id, not_deleted(AppRating)]
        stmt = (
            select(AppRating)
            .where(*filters)
            .order_by(AppRating.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        count_stmt = select(func.count(AppRating.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        rows = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[AppRatingOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def upsert_rating(self, app_id: UUID, body: AppRatingCreate) -> AppRatingOut:
        """已安装用户每应用一条评分，更新后重算 rating_avg。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise BadRequestError("仅已上架应用可评分")
        await self.require_installed(app_id)
        existing = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        if existing:
            existing.score = body.score
            existing.comment = body.comment
            rating = existing
        else:
            rating = AppRating(
                app_id=app_id,
                tenant_id=self.ctx.tenant_id,
                user_id=self.ctx.user_id,
                score=body.score,
                comment=body.comment,
            )
            self.db.add(rating)
        await self.db.flush()
        await self.refresh_rating_stats(app_id)
        return AppRatingOut.model_validate(rating)

    async def delete_my_rating(self, app_id: UUID) -> None:
        """删除当前用户对该应用的评分。"""
        rating = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        if not rating:
            raise NotFoundError("评分不存在")
        mark_deleted(rating)
        await self.db.flush()
        await self.refresh_rating_stats(app_id)
