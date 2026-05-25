"""
检索结果 rerank 精排。

链路
----
``retriever.search_kb_chunks``：
  1. ``compute_rerank_fetch_limit`` 扩大首轮召回数（候选池，默认最多 50）
  2. 向量 / 混合 / RRF 得到候选 hits
  3. 若 KB 配置了 ``rerank_model_config_id``，``apply_rerank_to_hits`` 调用 rerank API
  4. 按 ``top_n=limit`` 截断返回

rerank 模型通过 ``integrations.rerank.registry`` 适配各供应商 API。
"""

from __future__ import annotations

from typing import Any

from app.integrations.rerank.registry import rerank_documents_for_model
from app.models.model import ModelConfig

# KB 未配置 rerank_candidate_k 时的默认候选池上限
DEFAULT_CANDIDATE_K = 50


def compute_rerank_fetch_limit(
    limit: int,
    *,
    rerank_model: ModelConfig | None,
    candidate_k: int | None = None,
) -> int:
    """
    计算首轮向量/混合检索的 fetch 条数。

    无 rerank 时等于 ``limit``；有 rerank 时扩大到 min(max(limit*3, limit), pool)，
    以便精排前有足够候选。
    """
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
    """
    对候选 hits 调用 rerank 模型，按 relevance_score 重排。

    使用 hit 的 ``content``（若 KB API 已回填 PG 全文）或 ``content_preview`` 作为 document 文本；
    返回结果写入 ``score`` 与 ``score_rerank``。API 失败或空文档时回退 ``hits[:top_n]``。
    """
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
