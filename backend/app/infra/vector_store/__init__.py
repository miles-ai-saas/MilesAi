"""向量存储客户端（LangChain：weaviate / milvus / pgvector）。"""

from __future__ import annotations

from app.infra.vector_store.base import ChunkVectorRecord, VectorStore
from app.infra.vector_store.factory import get_vector_store

__all__ = [
    "ChunkVectorRecord",
    "VectorStore",
    "WeaviateVectorStore",
    "MilvusVectorStore",
    "PgVectorStore",
    "get_vector_store",
    "upsert_chunk_vector",
    "search_vectors",
    "delete_by_document",
    "delete_by_chunk_ids",
]


def __getattr__(name: str):
    if name == "WeaviateVectorStore":
        from app.infra.vector_store.weaviate import WeaviateVectorStore

        return WeaviateVectorStore
    if name == "MilvusVectorStore":
        from app.infra.vector_store.milvus import MilvusVectorStore

        return MilvusVectorStore
    if name == "PgVectorStore":
        from app.infra.vector_store.pgvector import PgVectorStore

        return PgVectorStore
    if name in (
        "upsert_chunk_vector",
        "search_vectors",
        "delete_by_document",
        "delete_by_chunk_ids",
    ):
        import app.rag.index.gateway as gateway

        return getattr(gateway, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
