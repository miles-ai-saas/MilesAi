"""向量存储客户端（LangChain：weaviate / milvus / pgvector）。

业务写入/检索请使用 app.rag.index.gateway，勿直接 import 具体 Store。
"""

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
    """延迟加载具体 Store 实现，避免未安装依赖时 import 失败。"""
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
