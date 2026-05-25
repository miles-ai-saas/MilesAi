"""Embedding provider 协议。"""

from __future__ import annotations

from typing import Protocol

from app.models.model import ModelConfig


class EmbeddingProvider(Protocol):
    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]: ...
