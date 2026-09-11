"""应用市场浏览与公共序列化。"""

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, NotFoundError
from app.models.meta.tag import EntityTagBinding, TagEntityType, TenantTag
from app.common.schema import PageParams, PageResult
from app.tenant.marketplace.models import (
    AppCategory,
    AppInstall,
    AppRating,
    MarketplaceApp,
    MarketplaceAppStatus,
    MarketplaceAppVisibility,
)
from app.core.soft_delete import not_deleted
from app.tenant.marketplace.schemas.marketplace import (
    AppCategoryOut,
    AppRatingOut,
    MarketplaceAppDetail,
    MarketplaceAppOut,
)
from app.tenant.tags.schemas.tag import TagRefOut
from app.tenant.tags.services.tag import TagService


class MarketplaceCatalogMixin:
    """应用市场浏览、详情与序列化。"""

    async def installed_app_ids(self) -> set[UUID]:
        """当前租户已安装的应用 ID 集合。"""
        stmt = select(AppInstall.app_id).where(AppInstall.tenant_id == self.ctx.tenant_id)
        return set((await self.db.execute(stmt)).scalars().all())

    def app_out(
        self,
        app: MarketplaceApp,
        *,
        installed: bool,
        category_name: str | None,
        tags: list[TagRefOut] | None = None,
    ) -> MarketplaceAppOut:
        """组装 ``MarketplaceAppOut``。"""
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
            category_name=category_name,
            tags=tags or [],
            installed=installed,
            review_note=app.review_note,
            submitted_at=app.submitted_at,
            reviewed_at=app.reviewed_at,
            created_at=app.created_at,
        )

    async def tags_map_for_apps(self, apps: list[MarketplaceApp]) -> dict[UUID, list[TagRefOut]]:
        """按发布方租户批量加载应用标签。"""
        if not apps:
            return {}
        tag_svc = TagService(self.db, self.ctx)
        by_tenant: dict[UUID, set[UUID]] = {}
        for app in apps:
            tid = app.publisher_tenant_id
            if tid is None:
                continue
            by_tenant.setdefault(tid, set()).add(app.id)
        out: dict[UUID, list[TagRefOut]] = {}
        for tenant_id, entity_ids in by_tenant.items():
            partial = await tag_svc.get_refs_map_for_tenant(TagEntityType.MARKETPLACE_APP, entity_ids, tenant_id)
            out.update(partial)
        return out

    def _plaza_tag_filter(self, tag_slugs: list[str]):
        """广场列表：按标签 slug 匹配发布方绑定（跨租户浏览）。"""
        if not tag_slugs:
            return None
        return exists(
            select(1)
            .select_from(EntityTagBinding)
            .join(TenantTag, TenantTag.id == EntityTagBinding.tag_id)
            .where(
                EntityTagBinding.entity_type == TagEntityType.MARKETPLACE_APP.value,
                EntityTagBinding.entity_id == MarketplaceApp.id,
                EntityTagBinding.tenant_id == MarketplaceApp.publisher_tenant_id,
                TenantTag.slug.in_(tag_slugs),
            )
        )

    def _plaza_visibility_filter(self):
        """广场：公开应用或本租户发布的租户内可见应用。"""
        return or_(
            MarketplaceApp.visibility == MarketplaceAppVisibility.PUBLIC.value,
            ((MarketplaceApp.visibility == MarketplaceAppVisibility.TENANT_ONLY.value) & (MarketplaceApp.publisher_tenant_id == self.ctx.tenant_id)),
        )

    async def app_out_with_tags(self, app: MarketplaceApp) -> MarketplaceAppOut:
        """单条应用 Out（含标签与安装态）。"""
        installed_ids = await self.installed_app_ids()
        tags_map = await self.tags_map_for_apps([app])
        return self.app_out(
            app,
            installed=app.id in installed_ids,
            category_name=app.category.name if app.category else None,
            tags=tags_map.get(app.id, []),
        )

    async def apps_to_out(self, apps: list[MarketplaceApp], *, installed_ids: set[UUID]) -> list[MarketplaceAppOut]:
        """批量组装 ``MarketplaceAppOut``；标签一次加载，避免逐条查询。"""
        tags_map = await self.tags_map_for_apps(apps)
        return [
            self.app_out(
                a,
                installed=a.id in installed_ids,
                category_name=a.category.name if a.category else None,
                tags=tags_map.get(a.id, []),
            )
            for a in apps
        ]

    async def get_app_or_raise(self, app_id: UUID) -> MarketplaceApp:
        """加载应用（含分类）；不存在则 404。"""
        stmt = select(MarketplaceApp).where(MarketplaceApp.id == app_id).options(selectinload(MarketplaceApp.category))
        app = (await self.db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise NotFoundError("应用不存在")
        return app

    async def list_categories(self) -> list[AppCategoryOut]:
        """列出应用分类。"""
        stmt = select(AppCategory).order_by(AppCategory.sort_order.asc(), AppCategory.name.asc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [AppCategoryOut.model_validate(r) for r in rows]

    async def list_apps(
        self,
        params: PageParams,
        *,
        category_slug: str | None = None,
        sort: str = "installs",
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[MarketplaceAppOut]:
        """分页列出已上架应用（支持分类、排序、标签）。"""
        installed_ids = await self.installed_app_ids()
        tag_slugs: list[str] = []
        if tag_ids:
            tag_slugs = await TagService(self.db, self.ctx).slugs_for_tag_ids(tag_ids)
        stmt = (
            select(MarketplaceApp)
            .where(
                MarketplaceApp.status == MarketplaceAppStatus.PUBLISHED,
                self._plaza_visibility_filter(),
            )
            .options(selectinload(MarketplaceApp.category))
        )
        count_filters = [
            MarketplaceApp.status == MarketplaceAppStatus.PUBLISHED,
            self._plaza_visibility_filter(),
        ]
        if category_slug:
            stmt = stmt.join(AppCategory, MarketplaceApp.category_id == AppCategory.id).where(AppCategory.slug == category_slug)
            count_filters.append(AppCategory.slug == category_slug)
        tag_filter = self._plaza_tag_filter(tag_slugs)
        if tag_filter is not None:
            stmt = stmt.where(tag_filter)
            count_filters.append(tag_filter)
        count_stmt = select(func.count(MarketplaceApp.id)).where(*count_filters)
        if category_slug:
            count_stmt = count_stmt.join(AppCategory, MarketplaceApp.category_id == AppCategory.id)
        total = await self.db.scalar(count_stmt)
        if sort == "rating":
            stmt = stmt.order_by(
                MarketplaceApp.rating_avg.desc(),
                MarketplaceApp.rating_count.desc(),
                MarketplaceApp.install_count.desc(),
            )
        else:
            stmt = stmt.order_by(MarketplaceApp.install_count.desc())
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        items = await self.apps_to_out(apps, installed_ids=installed_ids)
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def get_app(self, app_id: UUID) -> MarketplaceAppDetail:
        """应用详情（含 manifest、当前用户评分）。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            if app.publisher_tenant_id != self.ctx.tenant_id:
                raise NotFoundError("应用不存在或未发布")
        elif app.visibility == MarketplaceAppVisibility.TENANT_ONLY.value and app.publisher_tenant_id != self.ctx.tenant_id:
            raise NotFoundError("应用不存在或未发布")
        installed_ids = await self.installed_app_ids()
        cat_name = app.category.name if app.category else None
        tags_map = await self.tags_map_for_apps([app])
        base = self.app_out(
            app,
            installed=app.id in installed_ids,
            category_name=cat_name,
            tags=tags_map.get(app.id, []),
        )
        my_rating = await self.db.scalar(
            select(AppRating).where(
                AppRating.app_id == app_id,
                AppRating.tenant_id == self.ctx.tenant_id,
                AppRating.user_id == self.ctx.user_id,
                not_deleted(AppRating),
            )
        )
        return MarketplaceAppDetail(
            **base.model_dump(),
            manifest=app.manifest or {},
            my_rating=AppRatingOut.model_validate(my_rating) if my_rating else None,
        )

    async def list_my_apps(self, params: PageParams, *, tag_ids: list[UUID] | None = None) -> PageResult[MarketplaceAppOut]:
        """分页列出本租户发布的应用。"""
        installed_ids = await self.installed_app_ids()
        filters = [MarketplaceApp.publisher_tenant_id == self.ctx.tenant_id]
        stmt = select(MarketplaceApp).where(*filters).options(selectinload(MarketplaceApp.category)).order_by(MarketplaceApp.updated_at.desc())
        tag_filter = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.MARKETPLACE_APP, tag_ids or [])
        if tag_filter is not None:
            stmt = stmt.where(MarketplaceApp.id.in_(tag_filter))
            filters.append(MarketplaceApp.id.in_(tag_filter))
        count_stmt = select(func.count(MarketplaceApp.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        apps = (await self.db.execute(stmt)).scalars().all()
        items = await self.apps_to_out(apps, installed_ids=installed_ids)
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)

    async def get_own_app_or_raise(self, app_id: UUID) -> MarketplaceApp:
        """加载本租户发布的应用。"""
        app = await self.get_app_or_raise(app_id)
        if app.publisher_tenant_id != self.ctx.tenant_id:
            raise NotFoundError("应用不存在")
        return app

    async def require_installed(self, app_id: UUID) -> None:
        """校验当前租户已安装指定应用。"""
        installed = await self.db.scalar(
            select(AppInstall.id).where(
                AppInstall.tenant_id == self.ctx.tenant_id,
                AppInstall.app_id == app_id,
            )
        )
        if not installed:
            raise BadRequestError("安装该应用后才可评分")
