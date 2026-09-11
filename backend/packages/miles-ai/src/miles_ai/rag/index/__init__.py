"""
向量索引门面 re-export。

业务代码应 ``from miles_ai.rag.index import upsert_chunk_vector, search_vectors``，
勿 ``from miles_core.infra.vector_store import get_vector_store``。
"""

from miles_ai.rag.index.gateway import (
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
