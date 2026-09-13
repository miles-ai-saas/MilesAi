"""
Rerank Provider 注册表与分发。

链路
----
``search_kb_chunks``（扩大 fetch limit）
→ ``apply_rerank_to_hits``
→ ``rerank_documents_for_model`` → ``get_rerank_provider(invoke_mode)``

扩展：实现 ``RerankProvider`` 并 ``register_rerank_provider``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from miles_ai.integrations.rerank.model_meta import invoke_mode_from_model
from miles_ai.integrations.rerank.types import RerankHit
from miles_common.exceptions import BadRequestError
from miles_core.models.model import ModelConfig

if TYPE_CHECKING:
    from miles_ai.integrations.rerank.providers.base import RerankProvider

_PROVIDERS: dict[str, RerankProvider] = {}


def register_rerank_provider(mode: str, provider: RerankProvider) -> None:
    """注册 invoke_mode → RerankProvider。"""
    _PROVIDERS[mode.strip().lower()] = provider


def known_invoke_modes() -> frozenset[str]:
    """已注册的 rerank invoke_mode。"""
    return frozenset(_PROVIDERS)


def get_rerank_provider(mode: str) -> RerankProvider:
    """按 mode 获取 Provider。"""
    key = mode.strip().lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise BadRequestError(f"不支持的 rerank invoke_mode: {mode}")
    return provider


def rerank_documents_for_model(
    model: ModelConfig,
    *,
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[RerankHit]:
    """根据 ModelConfig 选择 Provider 对候选文档重排。"""
    if not documents:
        return []
    mode = invoke_mode_from_model(model)
    return get_rerank_provider(mode).rerank(
        model,
        query=query,
        documents=documents,
        top_n=top_n,
    )


def _register_builtin_providers() -> None:
    """模块加载时注册 DashScope 与 OpenAI 兼容 rerank。"""
    from miles_ai.integrations.rerank.constants import (
        INVOKE_MODE_DASHSCOPE,
        INVOKE_MODE_OPENAI_COMPATIBLE,
    )
    from miles_ai.integrations.rerank.providers.dashscope import DashScopeRerankProvider
    from miles_ai.integrations.rerank.providers.openai_compatible import (
        OpenAICompatibleRerankProvider,
    )

    register_rerank_provider(INVOKE_MODE_DASHSCOPE, DashScopeRerankProvider())
    register_rerank_provider(INVOKE_MODE_OPENAI_COMPATIBLE, OpenAICompatibleRerankProvider())


_register_builtin_providers()
