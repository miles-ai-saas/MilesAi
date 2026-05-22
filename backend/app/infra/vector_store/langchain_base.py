"""LangChain VectorStore 后端共用逻辑。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from app.infra.vector_store.documents import (
    chunk_record_to_document,
    known_embedding_dimensions,
)
from app.infra.vector_store.precomputed import PrecomputedEmbeddings


def upsert_add_texts(store: Any, record: ChunkVectorRecord, *, embedding_attr: str) -> str:
    """Milvus / Weaviate：预计算向量 + add_texts。"""
    dim = validate_dimension(len(record.vector))
    doc = chunk_record_to_document(record)
    setattr(store, embedding_attr, PrecomputedEmbeddings([record.vector]))
    obj_id = doc.id or str(record.chunk_id)
    return store.add_texts(
        texts=[doc.page_content],
        metadatas=[doc.metadata],
        ids=[obj_id],
    )[0]


def upsert_add_embeddings(store: Any, record: ChunkVectorRecord) -> str:
    """pgvector：add_embeddings。"""
    dim = validate_dimension(len(record.vector))
    doc = chunk_record_to_document(record)
    obj_id = doc.id or str(record.chunk_id)
    store.add_embeddings(
        texts=[doc.page_content],
        embeddings=[record.vector],
        metadatas=[doc.metadata],
        ids=[obj_id],
    )
    return obj_id


def foreach_dimension(
    get_store: Callable[[int], Any],
    fn: Callable[[Any], None],
) -> None:
    """对已缓存 / 常见维度执行操作（删除等）。"""
    for dim in known_embedding_dimensions():
        try:
            fn(get_store(dim))
        except Exception:
            continue
