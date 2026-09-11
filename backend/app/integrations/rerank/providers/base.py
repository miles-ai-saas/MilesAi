"""
Rerank Provider 协议。

返回 ``RerankHit`` 列表（``index`` 为输入 documents 下标，``relevance_score`` 为相关度）。
由 ``rag.retrieve.rerank.apply_rerank_to_hits`` 按 index 重排向量/混合检索候选。
"""

from __future__ import annotations

from typing import Protocol

from app.integrations.rerank.types import RerankHit
from app.models.model import ModelConfig


class RerankProvider(Protocol):
    """Rerank 后端实现协议。"""

    def rerank(
        self,
        model: ModelConfig,
        *,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """按 query 对 documents 重排，返回带原始下标的相关度结果（``top_n`` 为空则全量返回）。"""
        ...
