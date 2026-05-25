"""知识库分片向量索引门面（L2）。

业务侧 upsert/search/delete 统一由此模块调用；底层客户端为 infra.vector_store（Weaviate/Milvus/pgvector）。
勿从 infra.vector_store 导入 upsert_chunk_vector / search_vectors。
"""

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
    """写入或更新单条分片向量，返回外部向量 ID（存入 kb_vector_refs.vector_id）。"""
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
    """语义检索，返回 hit 列表（chunk_id、document_id、score 等）。"""
    return get_vector_store().search(
        query_vector, tenant_id=tenant_id, kb_id=kb_id, limit=limit
    )


def delete_by_document(document_id: UUID) -> None:
    """按 document_id 删除该文档在向量库中的全部分片。"""
    get_vector_store().delete_by_document(document_id)


def delete_by_chunk_ids(chunk_ids: list[str]) -> None:
    """按外部向量主键批量删除（重试入库前清理旧向量时使用）。"""
    get_vector_store().delete_by_chunk_ids(chunk_ids)
