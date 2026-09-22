"""
向量索引门面 re-export。

业务代码应 ``from miles_ai.rag.index import upsert_chunk_vector, upsert_chunk_vectors, search_vectors``，
勿 ``from miles_core.infra.vector_store import get_vector_store``。
"""

from miles_ai.rag.index.gateway import (
    ChunkVectorWrite,
    delete_by_chunk_ids,
    delete_by_document,
    search_vectors,
    upsert_chunk_vector,
    upsert_chunk_vectors,
)

__all__ = [
    "ChunkVectorWrite",
    "delete_by_chunk_ids",
    "delete_by_document",
    "search_vectors",
    "upsert_chunk_vector",
    "upsert_chunk_vectors",
]
