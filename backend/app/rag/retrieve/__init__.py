"""检索：单库 search_kb_chunks、多库 multi_kb、RRF 融合。"""

from app.rag.retrieve.hybrid import rrf_fuse
from app.rag.retrieve.retriever import (
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
    "rrf_fuse",
    "search_kb_chunks",
    "search_kb_chunks_sync",
]


def __getattr__(name: str):
    """延迟导出 multi_kb，避免循环 import。"""
    if name in ("search_multi_kb", "search_multi_kb_async"):
        from app.rag.retrieve import multi_kb

        return getattr(multi_kb, name)
    raise AttributeError(name)
