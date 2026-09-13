"""
向量存储客户端（L4：weaviate / milvus / pgvector）。

分层
----
- 业务 **只** 经 ``miles_ai.rag.index.gateway`` 读写
- LangChain 路径使用 ``precomputed.PrecomputedEmbeddings`` 避免二次 embed
- ``get_vector_store()`` 进程单例，切换 ``VECTOR_STORE_BACKEND`` 需重启 Worker/API
"""

from __future__ import annotations

from miles_core.infra.vector_store.base import ChunkVectorRecord, VectorStore
from miles_core.infra.vector_store.factory import get_vector_store

__all__ = [
    "ChunkVectorRecord",
    "MilvusVectorStore",
    "PgVectorStore",
    "VectorStore",
    "WeaviateVectorStore",
    "get_vector_store",
]


def __getattr__(name: str):
    """延迟加载具体 Store 实现，避免未安装依赖时 import 失败。"""
    if name == "WeaviateVectorStore":
        from miles_core.infra.vector_store.weaviate import WeaviateVectorStore

        return WeaviateVectorStore
    if name == "MilvusVectorStore":
        from miles_core.infra.vector_store.milvus import MilvusVectorStore

        return MilvusVectorStore
    if name == "PgVectorStore":
        from miles_core.infra.vector_store.pgvector import PgVectorStore

        return PgVectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
