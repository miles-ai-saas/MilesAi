"""Rerank provider 注册表。"""

from app.integrations.rerank.constants import (
    INVOKE_MODE_DASHSCOPE,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from app.integrations.rerank.model_meta import invoke_mode_from_model
from app.integrations.rerank.registry import known_invoke_modes, rerank_documents_for_model
from app.integrations.rerank.runtime import rerank_documents
from app.integrations.rerank.types import RerankHit

__all__ = [
    "INVOKE_MODE_DASHSCOPE",
    "INVOKE_MODE_OPENAI_COMPATIBLE",
    "RerankHit",
    "invoke_mode_from_model",
    "known_invoke_modes",
    "rerank_documents",
    "rerank_documents_for_model",
]
