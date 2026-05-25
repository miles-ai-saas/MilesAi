"""LiteLLM embedding（invoke_mode=litellm）。

委托 integrations.litellm.adapter.litellm_embed_texts；model 字符串由 resolve_litellm_model 解析。
"""

from __future__ import annotations

from app.integrations.litellm.adapter import litellm_embed_texts, resolve_litellm_model
from app.models.model import ModelConfig


class LiteLLMEmbeddingProvider:
    """通过 LiteLLM.embedding 批量向量化。"""

    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        """同步调用 LiteLLM，返回与 texts 等长的向量列表。"""
        return litellm_embed_texts(
            texts,
            model=resolve_litellm_model(model),
            api_key=model.api_key_encrypted,
            api_base=model.api_base,
        )
