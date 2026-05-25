"""
PostgreSQL 关键词检索（混合检索的「关键词路」）。

当向量库无原生 hybrid（Milvus/pgvector）时，用 PG ``DocumentChunk.content`` 的
ILIKE 子串匹配补关键词召回，再与向量路做 ``hybrid.rrf_fuse``。

注意：非全文 BM25，score_keyword 为按返回顺序递减的启发式分数。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.soft_delete import not_deleted
from app.models.kb import Document, DocumentChunk


def _keyword_stmt(tenant_id: UUID, kb_id: UUID, pattern: str, limit: int):
    """ILIKE 匹配分片正文，排除已软删文档。"""
    return (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.content,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.kb_id == kb_id,
            not_deleted(Document),
            DocumentChunk.content.ilike(pattern),
        )
        .order_by(DocumentChunk.created_at.desc())
        .limit(limit)
    )


def _rows_to_hits(rows, limit: int) -> list[dict]:
    """按查询顺序赋予递减 score_keyword（非 BM25）。"""
    hits: list[dict] = []
    for rank, row in enumerate(rows):
        chunk_id, document_id, content = row
        hits.append(
            {
                "chunk_id": str(chunk_id),
                "document_id": str(document_id),
                "content_preview": (content or "")[:500],
                "score": 1.0 - rank / max(limit, 1),
                "score_keyword": 1.0 - rank / max(limit, 1),
            }
        )
    return hits


async def search_chunks_by_keyword(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    kb_id: UUID,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """按分片正文子串匹配，返回与向量检索一致的 hit 结构。"""
    q = query.strip()
    if not q:
        return []

    pattern = f"%{q}%"
    rows = (await db.execute(_keyword_stmt(tenant_id, kb_id, pattern, limit))).all()
    return _rows_to_hits(rows, limit)


def search_chunks_by_keyword_sync(
    db: Session,
    *,
    tenant_id: UUID,
    kb_id: UUID,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """同步版关键词检索（_hybrid_sync 使用）。"""
    q = query.strip()
    if not q:
        return []
    pattern = f"%{q}%"
    rows = db.execute(_keyword_stmt(tenant_id, kb_id, pattern, limit)).all()
    return _rows_to_hits(rows, limit)
