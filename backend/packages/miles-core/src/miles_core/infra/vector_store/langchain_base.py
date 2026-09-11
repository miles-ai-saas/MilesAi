"""LangChain VectorStore 后端共用逻辑（Weaviate / pgvector）。

Milvus 使用 MilvusClient 直连，不经过本模块。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from miles_core.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from miles_core.infra.vector_store.documents import (
    chunk_record_to_document,
    known_embedding_dimensions,
)
from miles_core.infra.vector_store.precomputed import PrecomputedEmbeddings


def upsert_add_texts(store: Any, record: ChunkVectorRecord, *, embedding_attr: str) -> str:
    """
    Weaviate（及历史 Milvus LC 路径）：add_texts + 临时替换 store 的 embedding 实现。

    embedding_attr 多为 ``_embedding``；单次写入只绑定向量列表 [record.vector]。
    """
    validate_dimension(len(record.vector))
    doc = chunk_record_to_document(record)
    setattr(store, embedding_attr, PrecomputedEmbeddings([record.vector]))
    obj_id = doc.id or str(record.chunk_id)
    return store.add_texts(
        texts=[doc.page_content],
        metadatas=[doc.metadata],
        ids=[obj_id],
    )[0]


def upsert_add_embeddings(store: Any, record: ChunkVectorRecord) -> str:
    """pgvector：直接 add_embeddings，不经过 embed_documents 调模型。"""
    validate_dimension(len(record.vector))
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
