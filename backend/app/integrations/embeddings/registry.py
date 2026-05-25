"""向量化 provider 注册表与分发。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.model_meta import invoke_mode_from_model
from app.models.model import ModelConfig

if TYPE_CHECKING:
    from app.integrations.embeddings.providers.base import EmbeddingProvider

_PROVIDERS: dict[str, EmbeddingProvider] = {}


def register_embedding_provider(mode: str, provider: EmbeddingProvider) -> None:
    _PROVIDERS[mode.strip().lower()] = provider


def known_invoke_modes() -> frozenset[str]:
    return frozenset(_PROVIDERS)


def get_embedding_provider(mode: str) -> EmbeddingProvider:
    key = mode.strip().lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise BadRequestError(f"不支持的向量化 invoke_mode: {mode}")
    return provider


def embed_texts_for_model(model: ModelConfig, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    mode = invoke_mode_from_model(model)
    return get_embedding_provider(mode).embed_texts(model, texts)


def _register_builtin_providers() -> None:
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
