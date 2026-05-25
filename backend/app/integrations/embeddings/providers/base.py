"""Embedding provider 协议。"""

from __future__ import annotations

from typing import Protocol

from app.models.model import ModelConfig


class EmbeddingProvider(Protocol):
    """向量化后端实现协议（由 registry 按 invoke_mode 分发）。"""

    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]: ...
