"""向量化包对外导出（build_embeddings、embed_texts_for_model 等）。

入库/检索请用 integrations.langchain.embeddings，勿直接绕过 registry。
"""

from app.integrations.embeddings.constants import (
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_LOCAL,
    INVOKE_MODE_LITELLM,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from app.integrations.embeddings.model_meta import (
    embedding_dimension_from_model,
    invoke_mode_from_model,
)
from app.integrations.embeddings.registry import embed_texts_for_model, known_invoke_modes
from app.integrations.embeddings.runtime import build_embeddings

__all__ = [
    "EXTRA_EMBEDDING_DIMENSION",
    "INVOKE_MODE_LOCAL",
    "INVOKE_MODE_LITELLM",
    "INVOKE_MODE_OPENAI_COMPATIBLE",
    "build_embeddings",
    "embed_texts_for_model",
    "embedding_dimension_from_model",
    "invoke_mode_from_model",
    "known_invoke_modes",
]
