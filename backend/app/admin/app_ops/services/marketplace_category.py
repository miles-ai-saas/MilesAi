"""运营端应用市场分类 CRUD（表 mkt_categories，平台级）。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.marketplace_category import (
    MarketplaceCategoryCreate,
    MarketplaceCategoryOut,
    MarketplaceCategoryUpdate,
)
from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.common.slug import slugify
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.models.marketplace import AppCategory, MarketplaceApp


class AdminMarketplaceCategoryService:
    """应用市场分类 CRUD；删除前校验无应用引用（软删）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_categories(self) -> list[MarketplaceCategoryOut]:
        """列出未删除分类，并统计各分类下未删除应用数。"""
        stmt = select(AppCategory).where(not_deleted(AppCategory)).order_by(AppCategory.sort_order.asc(), AppCategory.name.asc())
        rows = (await self.db.execute(stmt)).scalars().all()
        out: list[MarketplaceCategoryOut] = []
        for row in rows:
            count = await self.db.scalar(
                select(func.count())
                .select_from(MarketplaceApp)
                .where(
                    MarketplaceApp.category_id == row.id,
                    not_deleted(MarketplaceApp),
                )
            )
            out.append(
                MarketplaceCategoryOut(
                    id=row.id,
                    name=row.name,
                    slug=row.slug,
                    sort_order=row.sort_order,
                    app_count=count or 0,
                )
            )
        return out

    async def create(self, body: MarketplaceCategoryCreate) -> MarketplaceCategoryOut:
        """创建分类；slug 缺省由名称生成并校验唯一。"""
        slug = (body.slug or "").strip() or slugify(body.name)
        await self._ensure_slug_unique(slug)
        row = AppCategory(name=body.name.strip(), slug=slug, sort_order=body.sort_order)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return MarketplaceCategoryOut(
            id=row.id,
            name=row.name,
            slug=row.slug,
            sort_order=row.sort_order,
            app_count=0,
        )

    async def update(self, category_id: UUID, body: MarketplaceCategoryUpdate) -> MarketplaceCategoryOut:
        """按需更新分类名称/slug/排序；slug 变更时校验唯一。"""
        row = await self._get_or_raise(category_id)
        data = body.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            row.name = data["name"].strip()
        if "slug" in data and data["slug"]:
            slug = data["slug"].strip()
            await self._ensure_slug_unique(slug, exclude_id=row.id)
            row.slug = slug
        if "sort_order" in data and data["sort_order"] is not None:
            row.sort_order = data["sort_order"]
        await self.db.flush()
        await self.db.refresh(row)
        count = await self._app_count(row.id)
        return MarketplaceCategoryOut(
            id=row.id,
            name=row.name,
            slug=row.slug,
            sort_order=row.sort_order,
            app_count=count,
        )

    async def delete(self, category_id: UUID) -> None:
        """软删分类；仍有应用引用时抛 ``BadRequestError``。"""
        row = await self._get_or_raise(category_id)
        count = await self._app_count(row.id)
        if count > 0:
            raise BadRequestError(f"仍有 {count} 个应用引用此分类，请先调整应用分类后再删除")
        await mark_deleted(self.db, row)

    async def _app_count(self, category_id: UUID) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(MarketplaceApp)
                .where(
                    MarketplaceApp.category_id == category_id,
                    not_deleted(MarketplaceApp),
                )
            )
            or 0
        )

    async def _get_or_raise(self, category_id: UUID) -> AppCategory:
        row = await self.db.get(AppCategory, category_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("分类不存在")
        return row

    async def _ensure_slug_unique(self, slug: str, *, exclude_id: UUID | None = None) -> None:
        filters = [AppCategory.slug == slug, not_deleted(AppCategory)]
        if exclude_id:
            filters.append(AppCategory.id != exclude_id)
        exists = await self.db.scalar(select(AppCategory.id).where(*filters).limit(1))
        if exists:
            raise ConflictError(f"分类标识「{slug}」已存在")
