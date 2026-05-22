"""混合检索：RRF（Reciprocal Rank Fusion）融合多路排序结果。"""

from __future__ import annotations

from typing import Any

RRF_K = 60


def rrf_fuse(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    limit: int = 10,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """将多路检索结果按 RRF 分数合并，返回按 score 降序的 hit 列表。"""
    if not ranked_lists:
        return []
    if len(ranked_lists) == 1:
        return ranked_lists[0][:limit]

    fused: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}

    # source_idx=0 视为向量路，其余视为关键词路（用于 hit 上 score_vector / score_keyword）
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
