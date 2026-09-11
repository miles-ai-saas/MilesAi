"""种子脚本共用辅助（分类 lookup、租户枚举）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.soft_delete import not_deleted
from miles_core.models.meta.category import CategoryDomain, SysCategory
from miles_core.models.platform.tenant import Tenant


async def list_tenant_ids(session: AsyncSession) -> list:
    return list((await session.execute(select(Tenant.id))).scalars().all())


async def category_id_by_slug(
    session: AsyncSession,
    domain: CategoryDomain,
    slug: str | None,
):
    if not slug:
        return None
    return await session.scalar(
        select(SysCategory.id).where(
            SysCategory.domain == domain.value,
            SysCategory.slug == slug,
            not_deleted(SysCategory),
        )
    )
