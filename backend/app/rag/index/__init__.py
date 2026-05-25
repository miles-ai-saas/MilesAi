"""向量索引门面导出（业务请用 gateway，勿直连接 vector_store）。"""

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
