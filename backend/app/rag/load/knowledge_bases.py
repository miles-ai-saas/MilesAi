"""按租户加载知识库实体（RAG 检索 / 生成用）。

避免 rag 层 import tenant.kb.services；绑定校验（租户、软删）在此集中。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.common.exceptions import NotFoundError
from app.core.soft_delete import not_deleted
from app.models.kb import KnowledgeBase


async def load_kbs_for_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    kb_ids: list[str],
) -> list[KnowledgeBase]:
    if not kb_ids:
        return []
    uuids = [UUID(str(i)) for i in kb_ids]
    rows = (
        await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.id.in_(uuids),
                not_deleted(KnowledgeBase),
            )
        )
    ).scalars().all()
    found = {kb.id for kb in rows}
    missing = [uid for uid in uuids if uid not in found]
    if missing:
        raise NotFoundError("部分知识库不存在或无权访问")
    order = {uid: i for i, uid in enumerate(uuids)}
    return sorted(rows, key=lambda k: order.get(k.id, 0))


def load_kb_sync(db: Session, tenant_id: UUID, kb_id: UUID) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb or kb.tenant_id != tenant_id or kb.deleted_at is not None:
        raise NotFoundError("知识库不存在")
    return kb
