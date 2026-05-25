"""Rerank 结果项。"""

from __future__ import annotations

from typing import TypedDict


class RerankHit(TypedDict, total=False):
    index: int
    relevance_score: float
    document: str
