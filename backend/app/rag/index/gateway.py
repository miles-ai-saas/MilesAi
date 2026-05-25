"""
知识库分片向量索引门面（L2）。

职责
----
- 业务（ingest、删除文档、检索）**只**应 import 本模块的 ``upsert_chunk_vector`` /
  ``search_vectors`` / ``delete_*``，不要直接 ``from app.infra.vector_store import ...``。
- 底层实现由 ``VECTOR_STORE_BACKEND`` 切换：weaviate | milvus | pgvector（见 factory）。
- ``ChunkVectorRecord`` 在此组装，屏蔽各后端参数差异。

与检索的关系
------------
- 纯向量：``search_vectors`` → store.search
- 混合（hybrid）：``app.rag.retrieve.retriever`` 在 Weaviate 上可调 store.search_hybrid，
  其他后端则 gateway.search_vectors + PG 关键词 + RRF。
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
    """
    写入或更新单条分片向量。

    由 ``app.rag.pipeline.ingest`` 在分片 embedding 完成后调用。
    返回值写入 PG ``kb_vector_refs.vector_id``，供后续按 id 删除或对账。
    """
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
    """
    语义向量检索。

    返回 hit 列表，字段见 ``integrations.langchain.vector.documents._doc_to_hit_row``
    （chunk_id、document_id、score、score_vector 等）。
    """
    return get_vector_store().search(
        query_vector, tenant_id=tenant_id, kb_id=kb_id, limit=limit
    )


def delete_by_document(document_id: UUID) -> None:
    """删除文档时级联清理向量库中该 document 的全部分片。"""
    get_vector_store().delete_by_document(document_id)


def delete_by_chunk_ids(chunk_ids: list[str]) -> None:
    """
    按外部向量主键批量删除。

    用于入库重试、分片重建前清理旧 vector_id，避免 Milvus/Weaviate 残留。
    """
    get_vector_store().delete_by_chunk_ids(chunk_ids)
