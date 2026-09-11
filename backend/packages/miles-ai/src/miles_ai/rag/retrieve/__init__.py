"""
检索子包导出（L2）。

- ``search_kb_chunks*``：单 KB，内部 ``gateway.search_vectors`` + 可选 hybrid/rerank
- ``search_multi_kb_async``：多 KB 异步检索（``__getattr__`` 延迟导出，避免循环 import）
- ``rrf_fuse``：Milvus/pgvector 无原生 hybrid 时的向量+关键词融合

向量写入不在此包，见 ``rag.index.gateway`` / ``rag.pipeline``。
"""

from miles_ai.rag.retrieve.constants import RETRIEVAL_HYBRID, RETRIEVAL_VECTOR
from miles_ai.rag.retrieve.hybrid import rrf_fuse
from miles_ai.rag.retrieve.retriever import (
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
    if name == "search_multi_kb_async":
        from miles_ai.rag.retrieve import multi_kb

        return getattr(multi_kb, name)
    raise AttributeError(name)
