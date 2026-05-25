"""运营端 sys_categories：全平台全局分类维护。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.sys_category import (
    SysCategoryAdminCreate,
    SysCategoryAdminOut,
    SysCategoryAdminUpdate,
)
from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.models.category import CategoryDomain, SysCategory
from app.tenant.categories.services.category import slugify

DOMAINS = [d.value for d in CategoryDomain]


def _parse_domain(domain: str) -> str:
    d = domain.strip().lower()
    if d not in DOMAINS:
        raise BadRequestError(f"不支持的 domain: {domain}")
    return d


def _to_out(row: SysCategory) -> SysCategoryAdminOut:
    return SysCategoryAdminOut.model_validate(row)


class AdminSysCategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_domain(self, domain: str) -> list[SysCategoryAdminOut]:
        dom = _parse_domain(domain)
        stmt = (
            select(SysCategory)
            .where(SysCategory.domain == dom, not_deleted(SysCategory))
            .order_by(SysCategory.sort_order.asc(), SysCategory.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [_to_out(r) for r in rows]

    async def create(self, domain: str, body: SysCategoryAdminCreate) -> SysCategoryAdminOut:
        dom = _parse_domain(domain)
        slug = (body.slug or "").strip() or slugify(body.name)
        await self._ensure_slug_unique(slug, dom)
        row = SysCategory(
            domain=dom,
            name=body.name.strip(),
            slug=slug,
            sort_order=body.sort_order,
            is_system=True,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return _to_out(row)

    async def update(self, category_id: UUID, body: SysCategoryAdminUpdate) -> SysCategoryAdminOut:
        row = await self._get_or_raise(category_id)
        data = body.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            data["name"] = data["name"].strip()
        if "slug" in data and data["slug"]:
            data["slug"] = data["slug"].strip()
            await self._ensure_slug_unique(data["slug"], row.domain, exclude_id=row.id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return _to_out(row)

    async def delete(self, category_id: UUID) -> None:
        row = await self._get_or_raise(category_id)
        await mark_deleted(self.db, row)

    async def _get_or_raise(self, category_id: UUID) -> SysCategory:
        row = await self.db.get(SysCategory, category_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("分类不存在")
        return row

    async def _ensure_slug_unique(
        self, slug: str, domain: str, *, exclude_id: UUID | None = None
    ) -> None:
        filters = [
            SysCategory.domain == domain,
            SysCategory.slug == slug,
            not_deleted(SysCategory),
        ]
        if exclude_id:
            filters.append(SysCategory.id != exclude_id)
        if await self.db.scalar(select(SysCategory.id).where(*filters).limit(1)):
            raise ConflictError(f"分类标识「{slug}」已存在")
