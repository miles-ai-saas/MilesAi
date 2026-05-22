"""知识库检索模式解析与统一检索入口。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infra.vector_store import get_vector_store, search_vectors
from app.infra.vector_store.hybrid import rrf_fuse
from app.models.kb import KnowledgeBase
from app.tenant.kb.services.keyword_search import (
    search_chunks_by_keyword,
    search_chunks_by_keyword_sync,
)

RETRIEVAL_VECTOR = "vector"
RETRIEVAL_HYBRID = "hybrid"
VALID_MODES = frozenset({RETRIEVAL_VECTOR, RETRIEVAL_HYBRID})


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
) -> list[dict[str, Any]]:
    """按检索模式查询分片 hit（含 chunk_id / document_id / score）。"""
    effective = resolve_retrieval_mode(kb, mode)
    if effective == RETRIEVAL_VECTOR:
        hits = search_vectors(
            query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=limit,
        )
        for h in hits:
            h.setdefault("score_vector", h.get("score"))
        return hits

    backend = get_settings().vector_store_backend.lower()
    store = get_vector_store()
    alpha = float(kb.hybrid_alpha if kb.hybrid_alpha is not None else 0.5)
    alpha = max(0.0, min(1.0, alpha))

    if backend == "weaviate" and hasattr(store, "search_hybrid"):
        return store.search_hybrid(
            query,
            query_vector=query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=limit,
            alpha=alpha,
        )

    fetch_n = min(limit * 3, 50)
    vector_hits = search_vectors(
        query_vector,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        limit=fetch_n,
    )
    for h in vector_hits:
        h["score_vector"] = h.get("score")

    keyword_hits = await search_chunks_by_keyword(
        db,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        query=query,
        limit=fetch_n,
    )
    if not keyword_hits:
        return vector_hits[:limit]
    if not vector_hits:
        return keyword_hits[:limit]
    return rrf_fuse([vector_hits, keyword_hits], limit=limit)


def _hybrid_sync(
    db: Session,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    backend = get_settings().vector_store_backend.lower()
    store = get_vector_store()
    alpha = float(kb.hybrid_alpha if kb.hybrid_alpha is not None else 0.5)
    alpha = max(0.0, min(1.0, alpha))

    if backend == "weaviate" and hasattr(store, "search_hybrid"):
        return store.search_hybrid(
            query,
            query_vector=query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=limit,
            alpha=alpha,
        )

    fetch_n = min(limit * 3, 50)
    vector_hits = search_vectors(
        query_vector,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        limit=fetch_n,
    )
    for h in vector_hits:
        h["score_vector"] = h.get("score")
    keyword_hits = search_chunks_by_keyword_sync(
        db,
        tenant_id=kb.tenant_id,
        kb_id=kb.id,
        query=query,
        limit=fetch_n,
    )
    if not keyword_hits:
        return vector_hits[:limit]
    if not vector_hits:
        return keyword_hits[:limit]
    return rrf_fuse([vector_hits, keyword_hits], limit=limit)


def search_kb_chunks_sync(
    db: Session,
    *,
    kb: KnowledgeBase,
    query: str,
    query_vector: list[float],
    limit: int,
    mode: str = "default",
) -> list[dict[str, Any]]:
    effective = resolve_retrieval_mode(kb, mode)
    if effective == RETRIEVAL_VECTOR:
        hits = search_vectors(
            query_vector,
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            limit=limit,
        )
        for h in hits:
            h.setdefault("score_vector", h.get("score"))
        return hits
    return _hybrid_sync(
        db, kb=kb, query=query, query_vector=query_vector, limit=limit
    )
