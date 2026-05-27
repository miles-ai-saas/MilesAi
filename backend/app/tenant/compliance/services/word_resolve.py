"""
词条解析、扫描词表合并（BLOCK 优先）。

调用方
------
- ``CompliancePipeline`` / ``intercept``：Agent 对话敏感词扫描
- ``compliance_nodes.compliance_check``：画布 ComplianceCheck 节点
- 词库 CRUD：``get_or_create_entry`` 去重创建词条行
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import not_deleted
from app.tenant.compliance.models import (
    COMPLIANCE_SCOPE_TENANT,
    ComplianceLibraryBinding,
    LibraryWordBinding,
    SensitiveAction,
    SensitiveWordEntry,
    WordLibrary,
)


def merge_scan_words(pairs: list[tuple[str, SensitiveAction]]) -> list[tuple[str, SensitiveAction]]:
    """同一词面多次出现时 BLOCK 覆盖 WARN。"""
    merged: dict[str, SensitiveAction] = {}
    for word, action in pairs:
        w = word.strip().lower()
        if not w:
            continue
        if w not in merged or action == SensitiveAction.BLOCK:
            merged[w] = action
    return [(w, a) for w, a in merged.items()]


async def load_tenant_scan_words(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[tuple[str, SensitiveAction]]:
    """仅加载已绑定且启用的词库中的启用词条。"""
    bound_lib_ids = (
        await db.execute(
            select(ComplianceLibraryBinding.library_id).where(
                ComplianceLibraryBinding.tenant_id == tenant_id,
                ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
                not_deleted(ComplianceLibraryBinding),
            )
        )
    ).scalars().all()
    if not bound_lib_ids:
        return []

    active_libs = (
        await db.execute(
            select(WordLibrary.id).where(
                WordLibrary.id.in_(bound_lib_ids),
                WordLibrary.tenant_id == tenant_id,
                WordLibrary.is_active.is_(True),
                not_deleted(WordLibrary),
            )
        )
    ).scalars().all()
    if not active_libs:
        return []

    stmt = (
        select(SensitiveWordEntry.word, LibraryWordBinding.action)
        .join(LibraryWordBinding, LibraryWordBinding.entry_id == SensitiveWordEntry.id)
        .where(
            LibraryWordBinding.library_id.in_(active_libs),
            LibraryWordBinding.is_active.is_(True),
            not_deleted(LibraryWordBinding),
            not_deleted(SensitiveWordEntry),
            SensitiveWordEntry.tenant_id == tenant_id,
        )
    )
    rows = (await db.execute(stmt)).all()
    return merge_scan_words([(r[0], r[1]) for r in rows])


async def get_or_create_entry(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    word: str,
) -> SensitiveWordEntry:
    """按租户 + 词面查找或新建 ``SensitiveWordEntry``（未绑定词库前仅占位）。"""
    normalized = word.strip()
    existing = (
        await db.execute(
            select(SensitiveWordEntry).where(
                SensitiveWordEntry.tenant_id == tenant_id,
                SensitiveWordEntry.word == normalized,
                not_deleted(SensitiveWordEntry),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    row = SensitiveWordEntry(tenant_id=tenant_id, word=normalized)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
