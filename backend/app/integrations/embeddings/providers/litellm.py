"""
LiteLLM 统一向量化（``invoke_mode=litellm``）。

将 ``ModelConfig`` 解析为 ``provider/model_name`` 后调用 ``litellm.embedding``；
适合多厂商共用一套配置，或 ``extra.litellm_model`` 显式指定完整 model 串。

对话类模型仍走 ``integrations.litellm.adapter.litellm_chat_completion``，勿混用。
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
