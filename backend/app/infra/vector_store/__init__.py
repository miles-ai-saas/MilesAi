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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
