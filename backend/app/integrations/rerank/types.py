"""Rerank 结果项。"""

from __future__ import annotations

from typing import TypedDict


class RerankHit(TypedDict, total=False):
    """单条重排结果：原候选下标 + 相关度分数。"""

    index: int
    relevance_score: float
    document: str
