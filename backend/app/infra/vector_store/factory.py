"""向量库客户端工厂（L4）。

进程内单例；VECTOR_STORE_BACKEND 变更需重启。索引写删请走 app.rag.index.gateway。

集合/类名前缀（各后端实现不同，勿强行统一）：
- pgvector：``milesai_kb_{dimension}``（见 ``pgvector.COLLECTION_PREFIX``）
- milvus：``document_chunk_{dimension}``（见 ``milvus.COLLECTION_PREFIX``）
- weaviate：固定类名 ``DocumentChunk``（见 ``weaviate.CLASS_NAME``）
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.infra.vector_store.base import VectorStore

_BACKENDS = frozenset({"weaviate", "pgvector", "milvus"})


@lru_cache
def get_vector_store() -> VectorStore:
    """按 VECTOR_STORE_BACKEND 返回单例向量库客户端（weaviate/pgvector/milvus）。"""
    name = get_settings().vector_store_backend.strip().lower()
    if name not in _BACKENDS:
        raise ValueError(f"不支持的 VECTOR_STORE_BACKEND={name!r}，可选: {', '.join(sorted(_BACKENDS))}")
    # 延迟 import，避免未启用后端时加载对应客户端 SDK
    if name == "weaviate":
        from app.infra.vector_store.weaviate import WeaviateVectorStore

        return WeaviateVectorStore()
    if name == "pgvector":
        from app.infra.vector_store.pgvector import PgVectorStore

        return PgVectorStore()
    # 默认 milvus：MilvusClient 直连，不经 LangChain ORM
    from app.infra.vector_store.milvus import MilvusVectorStore

    return MilvusVectorStore()
