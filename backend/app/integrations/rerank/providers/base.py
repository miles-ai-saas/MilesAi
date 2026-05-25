"""Rerank provider 协议。"""

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
    ) -> list[RerankHit]: ...
