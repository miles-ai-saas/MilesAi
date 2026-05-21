"""文档衍生数据清理：vector_refs、document_chunks、Weaviate 向量。"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.weaviate_store import delete_by_document
from app.models.kb import DocumentChunk, VectorRef


async def _chunk_ids_for_document_async(db: AsyncSession, document_id: UUID) -> list[UUID]:
    result = await db.execute(
        select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    )
    return list(result.scalars().all())


def clear_document_derived_data_sync(db: Session, document_id: UUID) -> None:
    """同步会话（Celery ingest）清理 chunk / vector_ref / Weaviate。"""
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
    """异步会话（API 删除）清理 chunk / vector_ref / Weaviate。"""
    chunk_ids = await _chunk_ids_for_document_async(db, document_id)
    if chunk_ids:
        await db.execute(delete(VectorRef).where(VectorRef.chunk_id.in_(chunk_ids)))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    delete_by_document(document_id)
