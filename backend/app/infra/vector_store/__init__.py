"""向量存储层：默认 Weaviate，可扩展 pgvector / Milvus。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infra.vector_store.base import ChunkVectorRecord, VectorStore

__all__ = [
    "ChunkVectorRecord",
    "VectorStore",
    "WeaviateVectorStore",
    "MilvusVectorStore",
    "get_vector_store",
    "upsert_chunk_vector",
    "search_vectors",
    "delete_by_document",
    "delete_by_chunk_ids",
]


def __getattr__(name: str):
    if name == "get_vector_store":
        from app.infra.vector_store.factory import get_vector_store as _fn

        return _fn
    if name == "WeaviateVectorStore":
        from app.infra.vector_store.weaviate import WeaviateVectorStore

        return WeaviateVectorStore
    if name == "MilvusVectorStore":
        from app.infra.vector_store.milvus import MilvusVectorStore

        return MilvusVectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _store():
    from app.infra.vector_store.factory import get_vector_store

    return get_vector_store()


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
    """写入向量库，返回外部向量 ID（存入 `kb_vector_refs.vector_id`）。"""
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
    return _store().upsert_chunk(record)


def search_vectors(
    query_vector: list[float],
    *,
    tenant_id: UUID,
    kb_id: UUID | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return _store().search(
        query_vector, tenant_id=tenant_id, kb_id=kb_id, limit=limit
    )


def delete_by_document(document_id: UUID) -> None:
    _store().delete_by_document(document_id)


def delete_by_chunk_ids(chunk_ids: list[str]) -> None:
    _store().delete_by_chunk_ids(chunk_ids)
