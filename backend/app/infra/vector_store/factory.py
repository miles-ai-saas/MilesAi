"""向量存储工厂。"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.infra.vector_store.base import VectorStore

_BACKENDS = frozenset({"weaviate", "pgvector", "pg_vector", "milvus"})


@lru_cache
def get_vector_store() -> VectorStore:
    name = get_settings().vector_store_backend.strip().lower()
    if name not in _BACKENDS:
        raise ValueError(
            f"不支持的 VECTOR_STORE_BACKEND={name!r}，"
            f"可选: {', '.join(sorted(_BACKENDS))}"
        )
    if name == "weaviate":
        from app.infra.vector_store.weaviate import WeaviateVectorStore

        return WeaviateVectorStore()
    if name in ("pgvector", "pg_vector"):
        from app.infra.vector_store.pgvector import PgVectorStore

        return PgVectorStore()
    from app.infra.vector_store.milvus import MilvusVectorStore

    return MilvusVectorStore()
