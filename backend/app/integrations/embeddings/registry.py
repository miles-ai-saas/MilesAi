"""向量化 provider 注册表与分发。

链路：build_embeddings → ModelConfigEmbeddings → embed_texts_for_model
     → invoke_mode → OpenAICompatible / LiteLLM / Local。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.model_meta import invoke_mode_from_model
from app.models.model import ModelConfig

if TYPE_CHECKING:
    from app.integrations.embeddings.providers.base import EmbeddingProvider

_PROVIDERS: dict[str, EmbeddingProvider] = {}


def register_embedding_provider(mode: str, provider: EmbeddingProvider) -> None:
    """注册 invoke_mode → Provider 实现。"""
    _PROVIDERS[mode.strip().lower()] = provider


def known_invoke_modes() -> frozenset[str]:
    """返回已注册的 invoke_mode 集合。"""
    return frozenset(_PROVIDERS)


def get_embedding_provider(mode: str) -> EmbeddingProvider:
    """按 mode 获取 Provider，未知 mode 抛 BadRequestError。"""
    key = mode.strip().lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise BadRequestError(f"不支持的向量化 invoke_mode: {mode}")
    return provider


def embed_texts_for_model(model: ModelConfig, texts: list[str]) -> list[list[float]]:
    """根据 ModelConfig 选择 Provider 并批量向量化。"""
    if not texts:
        return []
    mode = invoke_mode_from_model(model)
    return get_embedding_provider(mode).embed_texts(model, texts)


def _register_builtin_providers() -> None:
    """模块加载时注册内置 Provider。"""
    from app.integrations.embeddings.constants import (
        INVOKE_MODE_LITELLM,
        INVOKE_MODE_LOCAL,
        INVOKE_MODE_OPENAI_COMPATIBLE,
    )
    from app.integrations.embeddings.providers.litellm import LiteLLMEmbeddingProvider
    from app.integrations.embeddings.providers.local import LocalEmbeddingProvider
    from app.integrations.embeddings.providers.openai_compatible import (
        OpenAICompatibleEmbeddingProvider,
    )

    register_embedding_provider(INVOKE_MODE_LOCAL, LocalEmbeddingProvider())
    register_embedding_provider(
        INVOKE_MODE_OPENAI_COMPATIBLE, OpenAICompatibleEmbeddingProvider()
    )
    register_embedding_provider(INVOKE_MODE_LITELLM, LiteLLMEmbeddingProvider())


_register_builtin_providers()
