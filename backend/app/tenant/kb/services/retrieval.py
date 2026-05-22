"""兼容转发 → app.rag.retrieve（新代码请直接 import rag）。"""

from app.rag.retrieve import (
    RETRIEVAL_HYBRID,
    RETRIEVAL_VECTOR,
    resolve_retrieval_mode,
    search_kb_chunks,
    search_kb_chunks_sync,
)

__all__ = [
    "RETRIEVAL_HYBRID",
    "RETRIEVAL_VECTOR",
    "resolve_retrieval_mode",
    "search_kb_chunks",
    "search_kb_chunks_sync",
]
