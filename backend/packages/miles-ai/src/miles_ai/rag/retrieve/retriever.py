"""
知识库检索模式解析与统一检索入口。

模式（``KnowledgeBase.retrieval_mode`` / 请求参数）
-------------------------------------------------
- **vector**：``gateway.search_vectors``，纯语义向量。
- **hybrid**：
  - Weaviate：``store.search_hybrid``（BM25 + 向量，``hybrid_alpha`` 调节）
  - Milvus/pgvector：``search_vectors`` + ``keyword`` + ``hybrid.rrf_fuse``

可选 **rerank**：见 ``rerank.compute_rerank_fetch_limit`` / ``apply_rerank_to_hits``。

Agent 多 KB 场景见 ``multi_kb.search_kb`` / ``search_kb_async``。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_core.infra.vector_store.factory import get_vector_store
from miles_core.models.kb import KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_ai.rag.index.gateway import search_vectors
from miles_ai.rag.retrieve.hybrid import rrf_fuse
from miles_ai.rag.retrieve.keyword import (
    search_chunks_by_keyword,
    search_chunks_by_keyword_sync,
)
from miles_ai.rag.retrieve.constants import (
    RETRIEVAL_VECTOR,
    VALID_RETRIEVAL_MODES,
)
from miles_ai.rag.retrieve.rerank import apply_rerank_to_hits, compute_rerank_fetch_limit

VALID_MODES = VALID_RETRIEVAL_MODES


def resolve_retrieval_mode(kb: KnowledgeBase, request_mode: str | None) -> str:
    """request_mode=default 时使用 KB 配置。"""
    if request_mode and request_mode != "default":
        if request_mode not in VALID_MODES:
            return kb.retrieval_mode or RETRIEVAL_VECTOR
        return request_mode
    mode = (kb.retrieval_mode or RETRIEVAL_VECTOR).lower()
    return mode if mode in VALID_MODES else RETRIEVAL_VECTOR


async def search_kb_chunks(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    limit: int,
    mode: str,
    rerank_model: ModelConfig | None = None,
) -> list[dict[str, Any]]:
    """
    按检索模式查询分片 hit（含 chunk_id / document_id / score）。

    流程：解析 mode → 向量/混合召回 → 可选 rerank 截断到 limit。
    """
    fetch_limit = compute_rerank_fetch_limit(
        limit,
        rerank_model=rerank_model,
        candidate_k=kb.rerank_candidate_k,
    )
    effective = resolve_retrieval_mode(kb, mode)
    # 纯向量：gateway.search_vectors，各 VECTOR_STORE_BACKEND 行为一致
    if effective == RETRIEVAL_VECTOR:
        hits = search_vectors(
            query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=fetch_limit,
        )
        for h in hits:
            h.setdefault("score_vector", h.get("score"))
    # --- 混合：Weaviate 原生 BM25+向量；alpha 来自 kb.hybrid_alpha ---
    elif hasattr(get_vector_store(), "search_hybrid"):
        store = get_vector_store()
        alpha = float(kb.hybrid_alpha if kb.hybrid_alpha is not None else 0.5)
        alpha = max(0.0, min(1.0, alpha))
        hits = store.search_hybrid(
            query,
            query_vector=query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=fetch_limit,
            alpha=alpha,
        )
    # --- 混合：Milvus/pgvector 无 search_hybrid → 向量 + PG 关键词 RRF ---
    else:
        hits = await _hybrid_rrf(
            db,
            kb=kb,
            query=query,
            query_vector=query_vector,
            fetch_limit=fetch_limit,
        )

    if rerank_model is not None:
        return apply_rerank_to_hits(
            hits,
            query=query,
            rerank_model=rerank_model,
            top_n=limit,
        )
    return hits[:limit]


async def _hybrid_rrf(
    db: AsyncSession,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    fetch_limit: int,
) -> list[dict[str, Any]]:
    """向量检索 + PG 关键词检索，RRF 融合（向量库无 search_hybrid 时）。"""
    vector_hits = search_vectors(
        query_vector,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        limit=fetch_limit,
    )
    for h in vector_hits:
        h["score_vector"] = h.get("score")

    keyword_hits = await search_chunks_by_keyword(
        db,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        query=query,
        limit=fetch_limit,
    )
    if not keyword_hits:
        return vector_hits
    if not vector_hits:
        return keyword_hits
    return rrf_fuse([vector_hits, keyword_hits], limit=fetch_limit)


def _hybrid_sync(
    db: Session,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    fetch_limit: int,
) -> list[dict[str, Any]]:
    """同步版混合检索（脚本或 Worker 内调用）。"""
    store = get_vector_store()
    alpha = float(kb.hybrid_alpha if kb.hybrid_alpha is not None else 0.5)
    alpha = max(0.0, min(1.0, alpha))

    if hasattr(store, "search_hybrid"):
        return store.search_hybrid(
            query,
            query_vector=query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=fetch_limit,
            alpha=alpha,
        )

    vector_hits = search_vectors(
        query_vector,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        limit=fetch_limit,
    )
    for h in vector_hits:
        h["score_vector"] = h.get("score")
    keyword_hits = search_chunks_by_keyword_sync(
        db,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        query=query,
        limit=fetch_limit,
    )
    if not keyword_hits:
        return vector_hits
    if not vector_hits:
        return keyword_hits
    return rrf_fuse([vector_hits, keyword_hits], limit=fetch_limit)


def search_kb_chunks_sync(
    db: Session,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    limit: int,
    mode: str = "default",
    rerank_model: ModelConfig | None = None,
) -> list[dict[str, Any]]:
    """同步检索入口，语义同 search_kb_chunks。"""
    fetch_limit = compute_rerank_fetch_limit(
        limit,
        rerank_model=rerank_model,
        candidate_k=kb.rerank_candidate_k,
    )
    effective = resolve_retrieval_mode(kb, mode)
    if effective == RETRIEVAL_VECTOR:
        hits = search_vectors(
            query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=fetch_limit,
        )
        for h in hits:
            h.setdefault("score_vector", h.get("score"))
    else:
        hits = _hybrid_sync(
            db,
            kb=kb,
            query=query,
            query_vector=query_vector,
            fetch_limit=fetch_limit,
        )

    if rerank_model is not None:
        return apply_rerank_to_hits(
            hits,
            query=query,
            rerank_model=rerank_model,
            top_n=limit,
        )
    return hits[:limit]
