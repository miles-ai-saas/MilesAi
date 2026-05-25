"""
混合检索：RRF（Reciprocal Rank Fusion）融合多路排序结果。

使用场景
--------
当 ``VECTOR_STORE_BACKEND`` 为 milvus/pgvector（无 ``search_hybrid``）且 KB
``retrieval_mode=hybrid`` 时，``retriever._hybrid_rrf`` 合并：
  - 路 0：``gateway.search_vectors`` 语义向量
  - 路 1：``keyword.search_chunks_by_keyword`` PG ILIKE 关键词

Weaviate 后端通常走原生 ``search_hybrid``，不经过本模块。
"""

from __future__ import annotations

from typing import Any

# RRF 平滑常数，越大则高排名项优势越弱（业界常用 60）
RRF_K = 60


def rrf_fuse(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    limit: int = 10,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """
    将多路检索结果按 RRF 分数合并。

    分数：对每个 chunk_id，``sum( 1 / (k + rank + 1) )``，rank 从 0 起。
    输出 hit 的 ``score`` 为融合分；``score_vector`` / ``score_keyword`` 保留各路原始分。
    """
    if not ranked_lists:
        return []
    if len(ranked_lists) == 1:
        return ranked_lists[0][:limit]

    fused: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}

    # source_idx=0 约定为向量路，其余为关键词路（与 retriever._hybrid_rrf 调用顺序一致）
    for source_idx, hits in enumerate(ranked_lists):
        for rank, hit in enumerate(hits):
            chunk_id = hit.get("chunk_id")
            if not chunk_id:
                continue
            key = str(chunk_id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in fused:
                merged = dict(hit)
                merged["score_vector"] = None
                merged["score_keyword"] = None
                fused[key] = merged
            entry = fused[key]
            score_val = float(hit.get("score", 0))
            if source_idx == 0:
                entry["score_vector"] = score_val
            else:
                entry["score_keyword"] = score_val

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out: list[dict[str, Any]] = []
    for key, rrf_score in ordered[:limit]:
        hit = fused[key]
        hit["score"] = rrf_score
        out.append(hit)
    return out
