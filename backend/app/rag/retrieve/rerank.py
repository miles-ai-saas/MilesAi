"""检索结果 rerank 精排。

链路：search_kb_chunks 先扩大 fetch_limit → apply_rerank_to_hits 调用 rerank API 重排。
"""

from __future__ import annotations

from typing import Any

from app.integrations.rerank.registry import rerank_documents_for_model
from app.models.model import ModelConfig

DEFAULT_CANDIDATE_K = 50


def compute_rerank_fetch_limit(
    limit: int,
    *,
    rerank_model: ModelConfig | None,
    candidate_k: int | None = None,
) -> int:
    """有 rerank 时先多召回候选，再精排截断到 top_k。"""
    if rerank_model is None:
        return limit
    pool = candidate_k if candidate_k and candidate_k > 0 else DEFAULT_CANDIDATE_K
    return min(max(limit * 3, limit), pool)


def apply_rerank_to_hits(
    hits: list[dict[str, Any]],
    *,
    query: str,
    rerank_model: ModelConfig,
    top_n: int,
) -> list[dict[str, Any]]:
    """对向量/混合检索候选调用 rerank 模型，按 relevance_score 重排。"""
    if not hits or top_n <= 0:
        return []

    documents: list[str] = []
    for hit in hits:
        text = hit.get("content") or hit.get("content_preview") or ""
        documents.append(str(text))

    if not any(documents):
        return hits[:top_n]

    ranked = rerank_documents_for_model(
        rerank_model,
        query=query,
        documents=documents,
        top_n=min(top_n, len(documents)),
    )

    reordered: list[dict[str, Any]] = []
    for item in ranked:
        index = item.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(hits):
            continue
        hit = dict(hits[index])
        score = float(item["relevance_score"])
        hit["score"] = score
        hit["score_rerank"] = score
        reordered.append(hit)
    return reordered or hits[:top_n]
