"""
向量索引门面 re-export。

业务代码应 ``from app.rag.index import upsert_chunk_vector, search_vectors``，
勿 ``from app.infra.vector_store import get_vector_store``。
"""

from app.rag.index.gateway import (
    delete_by_chunk_ids,
    delete_by_document,
    search_vectors,
    upsert_chunk_vector,
)

__all__ = [
    "delete_by_chunk_ids",
    "delete_by_document",
    "search_vectors",
    "upsert_chunk_vector",
]
