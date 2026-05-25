"""LiteLLM embedding（OpenAI / Gemini 等 LiteLLM 已正式支持的 provider）。"""

from __future__ import annotations

from app.integrations.litellm.adapter import litellm_embed_texts, resolve_litellm_model
from app.models.model import ModelConfig


class LiteLLMEmbeddingProvider:
    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        return litellm_embed_texts(
            texts,
            model=resolve_litellm_model(model),
            api_key=model.api_key_encrypted,
            api_base=model.api_base,
        )
