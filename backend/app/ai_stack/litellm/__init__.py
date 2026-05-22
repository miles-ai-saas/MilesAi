"""LiteLLM 统一调用层（对话类模型）。"""

from app.ai_stack.litellm.adapter import (
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
