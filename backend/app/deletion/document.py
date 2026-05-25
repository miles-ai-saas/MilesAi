"""文档衍生数据清理：vector_refs、document_chunks、向量库记录。

入库重试与 API 删除均调用；同步版供 Celery pipeline，异步版供 HTTP。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.rag.index.gateway import delete_by_document
from app.models.kb import DocumentChunk, VectorRef


async def _chunk_ids_for_document_async(db: AsyncSession, document_id: UUID) -> list[UUID]:
    """查询文档下所有 chunk 主键。"""
    result = await db.execute(
        select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    )
    return list(result.scalars().all())


def clear_document_derived_data_sync(db: Session, document_id: UUID) -> None:
    """同步会话（Celery ingest）清理 chunk / vector_ref / 向量库。

    顺序：先 PG 关联表，再向量库按 document_id 删除（避免孤儿向量）。
    """
    chunk_ids = list(
        db.scalars(
            select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
        )
    )
    if chunk_ids:
        db.execute(delete(VectorRef).where(VectorRef.chunk_id.in_(chunk_ids)))
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    delete_by_document(document_id)


async def clear_document_derived_data_async(db: AsyncSession, document_id: UUID) -> None:
    """异步会话（API 删除）清理 chunk / vector_ref / 向量库。"""
    chunk_ids = await _chunk_ids_for_document_async(db, document_id)
    if chunk_ids:
        await db.execute(delete(VectorRef).where(VectorRef.chunk_id.in_(chunk_ids)))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    delete_by_document(document_id)
