"""
Rerank 集成包对外导出。

业务检索精排应经 ``rag.retrieve.rerank.apply_rerank_to_hits``，
勿直接调用 Provider，以保证失败回退与 score 字段一致。
"""

from miles_integrations.rerank.constants import (
    INVOKE_MODE_DASHSCOPE,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from miles_integrations.rerank.model_meta import invoke_mode_from_model
from miles_integrations.rerank.registry import known_invoke_modes, rerank_documents_for_model
from miles_integrations.rerank.runtime import rerank_documents
from miles_integrations.rerank.types import RerankHit

__all__ = [
    "INVOKE_MODE_DASHSCOPE",
    "INVOKE_MODE_OPENAI_COMPATIBLE",
    "RerankHit",
    "invoke_mode_from_model",
    "known_invoke_modes",
    "rerank_documents",
    "rerank_documents_for_model",
]
