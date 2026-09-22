"""LiteLLM 统一调用层（对话类模型）。

Embedding 同步路径亦导出 litellm_embed_texts；向量化 provider 可委托本模块。
"""

from miles_integrations.litellm.adapter import (
    CHAT_MODEL_TYPES,
    litellm_chat_completion,
    litellm_embed_texts,
    resolve_litellm_model,
)

__all__ = [
    "CHAT_MODEL_TYPES",
    "litellm_chat_completion",
    "litellm_embed_texts",
    "resolve_litellm_model",
]
