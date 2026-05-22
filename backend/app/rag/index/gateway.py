"""知识库分片向量索引门面（tenant/kb/chunk 语义）。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infra.vector_store.factory import get_vector_store
from app.infra.vector_store.base import ChunkVectorRecord


def upsert_chunk_vector(
    *,
    vector: list[float],
    tenant_id: UUID,
    kb_id: UUID,
    document_id: UUID,
    chunk_id: UUID,
    content_preview: str,
    object_key: str,
    page_no: int | None = None,
    vector_id: str | None = None,
) -> str:
    record = ChunkVectorRecord(
        vector=vector,
        tenant_id=tenant_id,
        kb_id=kb_id,
        document_id=document_id,
        chunk_id=chunk_id,
        content_preview=content_preview,
        object_key=object_key,
        page_no=page_no,
        external_id=vector_id,
    )
    return get_vector_store().upsert_chunk(record)


def search_vectors(
    query_vector: list[float],
    *,
    tenant_id: UUID,
    kb_id: UUID | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return get_vector_store().search(
        query_vector, tenant_id=tenant_id, kb_id=kb_id, limit=limit
    )


def delete_by_document(document_id: UUID) -> None:
    get_vector_store().delete_by_document(document_id)


def delete_by_chunk_ids(chunk_ids: list[str]) -> None:
    get_vector_store().delete_by_chunk_ids(chunk_ids)
