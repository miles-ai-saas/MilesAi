"""向量化运行时：从 ModelConfig 构建 LangChain Embeddings。

Provider 注册见 integrations.embeddings.registry；具体实现见 providers/。
"""

from __future__ import annotations

from copy import copy

from langchain_core.embeddings import Embeddings

from app.integrations.embeddings.constants import (
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_LOCAL,
)
from app.integrations.embeddings.model_meta import (
    embedding_dimension_from_model,
    ensure_embedding_model_type,
    invoke_mode_from_model,
)
from app.integrations.embeddings.providers.local import LocalEmbeddings
from app.integrations.embeddings.registry import embed_texts_for_model
from app.models.model import ModelConfig

# 兼容旧 import 路径
__all__ = [
    "EXTRA_EMBEDDING_DIMENSION",
    "INVOKE_MODE_LOCAL",
    "LocalEmbeddings",
    "ModelConfigEmbeddings",
    "build_embeddings",
    "embedding_dimension_from_model",
    "ensure_embedding_model_type",
    "invoke_mode_from_model",
    "merge_effective_embedding_model",
]


class ModelConfigEmbeddings(Embeddings):
    """按 ModelConfig.extra.invoke_mode 分发至已注册 provider。"""

    def __init__(self, model: ModelConfig) -> None:
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化（入库分片）。"""
        return embed_texts_for_model(self._model, texts)

    def embed_query(self, text: str) -> list[float]:
        """单条 query 向量化（检索）。"""
        return self.embed_documents([text])[0]


def build_embeddings(model: ModelConfig) -> Embeddings:
    """从 ModelConfig 构建 LangChain Embeddings 门面。"""
    ensure_embedding_model_type(model)
    return ModelConfigEmbeddings(model)


def merge_effective_embedding_model(
    model: ModelConfig,
    *,
    api_base: str | None = None,
    api_key_encrypted: str | None = None,
) -> ModelConfig:
    """合并 BYOK 后的副本，供调用使用。"""
    effective = copy(model)
    if api_base:
        effective.api_base = api_base
    if api_key_encrypted:
        effective.api_key_encrypted = api_key_encrypted
    return effective
