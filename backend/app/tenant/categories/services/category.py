"""租户工作台分类：只读列表与资源绑定校验（全平台全局字典）。"""

import hashlib
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext
from app.models.meta.category import CategoryDomain, SysCategory
from app.tenant.categories.meta import categories_meta_dict
from app.tenant.categories.schemas.category import CategoryOut
from app.tenant.categories.schemas.meta import CategoryMetaOut
from app.core.soft_delete import is_marked_deleted, not_deleted
from app.core.service import BaseService

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """将展示名转为 slug；供运营端与标签模块复用。"""
    raw = name.strip().lower()
    s = _SLUG_RE.sub("-", raw).strip("-")
    if s:
        return s[:64]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"c-{digest}"


def _parse_domain(domain: str) -> CategoryDomain:
    try:
        return CategoryDomain(domain.strip().lower())
    except ValueError as exc:
        raise BadRequestError(f"不支持的分类域: {domain}") from exc


class CategoryService(BaseService):
    """工作台分类只读服务（全局 sys_categories，无租户副本）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> CategoryMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return CategoryMetaOut.model_validate(categories_meta_dict())

    def _domain_value(self, domain: CategoryDomain | str) -> str:
        if isinstance(domain, CategoryDomain):
            return domain.value
        return _parse_domain(domain).value

    async def _get_or_raise(self, category_id: UUID) -> SysCategory:
        row = await self.db.get(SysCategory, category_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("分类不存在")
        return row

    async def validate_category_for_domain(self, category_id: UUID | None, domain: CategoryDomain) -> None:
        """创建/更新资源时校验 category_id 属于全局字典且 domain 一致。"""
        if not category_id:
            return
        row = await self._get_or_raise(category_id)
        if row.domain != domain.value:
            raise BadRequestError("分类与资源类型不匹配")

    async def list_categories(self, domain: str) -> list[CategoryOut]:
        """按域返回全平台系统分类（工作台 Tab/下拉）。"""
        dom = self._domain_value(domain)
        stmt = (
            select(SysCategory)
            .where(
                SysCategory.domain == dom,
                not_deleted(SysCategory),
            )
            .order_by(SysCategory.sort_order.asc(), SysCategory.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [CategoryOut.model_validate(r) for r in rows]

    async def get_category_name_map(self, domain: CategoryDomain, ids: set[UUID]) -> dict[UUID, str]:
        """批量解析分类 ID → 展示名。"""
        if not ids:
            return {}
        filters = [
            SysCategory.id.in_(ids),
            SysCategory.domain == domain.value,
            not_deleted(SysCategory),
        ]
        rows = (await self.db.execute(select(SysCategory.id, SysCategory.name).where(*filters))).all()
        return {r[0]: r[1] for r in rows}
