"""
Rerank API 单条结果（TypedDict）。

``apply_rerank_to_hits`` 用 ``index`` 映射回原始 hit 列表并写入 ``score_rerank``。
"""

from __future__ import annotations

from typing import TypedDict


class RerankHit(TypedDict, total=False):
    """单条重排结果：原候选下标 + 相关度分数。"""

    index: int
    relevance_score: float
    document: str
