"""工作台分类种子：全平台全局字典（幂等 upsert）。

数据：`scripts/seed/data/sys_categories_defaults.json`
命令：`milesai seed categories`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.agent import Agent
from miles_core.models.meta.category import CategoryDomain, SysCategory
from miles_portal.tenant.prompts.models import PromptTemplate
from miles_portal.tenant.skills.models import SkillPackage
from miles_portal.tenant.tools.models import Tool

_DEFAULTS_PATH = Path(__file__).resolve().parent / "data" / "sys_categories_defaults.json"

CategoryRow = tuple[str, str, int, bool]


def _load_defaults() -> dict[str, list[CategoryRow]]:
    if _DEFAULTS_PATH.is_file():
        raw: dict[str, Any] = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        out: dict[str, list[CategoryRow]] = {}
        for domain in ("agent", "prompt", "skill", "tool"):
            rows = raw.get(domain) or []
            out[domain] = [
                (
                    str(item["name"]),
                    str(item["slug"]),
                    int(item.get("sort_order", 0)),
                    bool(item.get("is_system", True)),
                )
                for item in rows
            ]
        return out
    return {"agent": [], "prompt": [], "skill": [], "tool": []}


DEFAULTS_BY_DOMAIN = _load_defaults()

_DEPRECATED_SLUGS = frozenset({"uncategorized"})


async def _purge_deprecated_categories(session: AsyncSession) -> int:
    """软删除种子中已移除的全局分类（如 uncategorized），并清空资源引用。"""
    from miles_core.soft_delete import mark_deleted

    stmt = select(SysCategory).where(
        SysCategory.slug.in_(_DEPRECATED_SLUGS),
        SysCategory.deleted_at.is_(None),
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return 0
    ids = [row.id for row in rows]
    for model in (Agent, PromptTemplate, SkillPackage, Tool):
        await session.execute(update(model).where(model.category_id.in_(ids)).values(category_id=None))
    for row in rows:
        await mark_deleted(session, row)
    return len(rows)


async def seed_categories(session: AsyncSession) -> None:
    """按 domain+slug 幂等写入全局分类（不区分租户、无 provision）。"""
    stats: dict[str, int] = {}
    for domain_key, rows in DEFAULTS_BY_DOMAIN.items():
        dom = CategoryDomain(domain_key)
        added = 0
        for name, slug, order, is_system in rows:
            exists = await session.scalar(
                select(SysCategory.id).where(
                    SysCategory.domain == dom.value,
                    SysCategory.slug == slug,
                )
            )
            if exists:
                continue
            session.add(
                SysCategory(
                    domain=dom.value,
                    name=name,
                    slug=slug,
                    sort_order=order,
                    is_system=is_system,
                )
            )
            added += 1
        stats[domain_key] = added
    purged = await _purge_deprecated_categories(session)
    await session.flush()
    print(f">>> categories seed (global): {stats}, purged: {purged}")
