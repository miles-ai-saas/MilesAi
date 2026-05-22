"""向量化运行时（ModelConfig 驱动）。"""

from app.integrations.embeddings.runtime import (
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_LOCAL,
    build_embeddings,
    embedding_dimension_from_model,
    invoke_mode_from_model,
)

__all__ = [
    "INVOKE_MODE_LOCAL",
    "EXTRA_EMBEDDING_DIMENSION",
    "build_embeddings",
    "embedding_dimension_from_model",
    "invoke_mode_from_model",
]
