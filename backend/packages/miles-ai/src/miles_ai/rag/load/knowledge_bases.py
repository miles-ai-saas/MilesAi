"""
按租户加载 ``KnowledgeBase`` ORM（RAG 检索 / 生成用）。

职责
----
- 校验 kb_id 属于 tenant_id 且未软删。
- 多 KB 时保持请求 ``kb_ids`` 顺序（Agent 展示与日志一致）。

避免 rag 子包直接依赖 ``tenant.kb.services``，减少循环 import。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_common.exceptions import NotFoundError
from miles_core.models.kb import KnowledgeBase
from miles_core.soft_delete import not_deleted


async def load_kbs_for_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    kb_ids: list[str],
) -> list[KnowledgeBase]:
    """按请求顺序加载多个 KB；缺失则 NotFoundError。"""
    if not kb_ids:
        return []
    uuids = [UUID(str(i)) for i in kb_ids]
    rows = (
        (
            await db.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.tenant_id == tenant_id,
                    KnowledgeBase.id.in_(uuids),
                    not_deleted(KnowledgeBase),
                )
            )
        )
        .scalars()
        .all()
    )
    found = {kb.id for kb in rows}
    missing = [uid for uid in uuids if uid not in found]
    if missing:
        raise NotFoundError("部分知识库不存在或无权访问")
    order = {uid: i for i, uid in enumerate(uuids)}
    return sorted(rows, key=lambda k: order.get(k.id, 0))


def load_kb_sync(db: Session, tenant_id: UUID, kb_id: UUID) -> KnowledgeBase:
    """同步加载单个 KB 并校验租户与未删除。"""
    kb = db.get(KnowledgeBase, kb_id)
    if not kb or kb.tenant_id != tenant_id or kb.deleted_at is not None:
        raise NotFoundError("知识库不存在")
    return kb
