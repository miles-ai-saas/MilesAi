"""向量化运行时：从 ModelConfig 构建 Embeddings（local BGE / LiteLLM）。

创建 KB 时用 embedding_dimension_from_model 固化维度；与 rag 入库/检索共用 build_embeddings。
"""

from __future__ import annotations

from copy import copy
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.integrations.litellm.adapter import litellm_embed_texts, resolve_litellm_model
from app.common.exceptions import BadRequestError
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType

INVOKE_MODE_LOCAL = "local"
EXTRA_EMBEDDING_DIMENSION = "embedding_dimension"
EXTRA_INVOKE_MODE = "invoke_mode"


def embedding_dimension_from_model(model: ModelConfig) -> int:
    extra = model.extra or {}
    dim = extra.get(EXTRA_EMBEDDING_DIMENSION)
    if isinstance(dim, int) and dim > 0:
        return dim
    raise BadRequestError(
        f"向量化模型「{model.name}」未配置 extra.embedding_dimension"
    )


def invoke_mode_from_model(model: ModelConfig) -> str:
    extra = model.extra or {}
    mode = extra.get(EXTRA_INVOKE_MODE)
    if isinstance(mode, str) and mode.strip():
        return mode.strip().lower()
    return "litellm"


def ensure_embedding_model_type(model: ModelConfig) -> None:
    if model.model_type != ModelCapabilityType.EMBEDDING.value:
        raise BadRequestError(
            f"模型「{model.name}」类型为 {model.model_type}，知识库须绑定向量化模型（embedding）"
        )


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class LocalEmbeddings(Embeddings):
    """本地 Sentence-Transformers。"""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoder = _load_sentence_transformer(self._model_name)
        vectors = encoder.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class ModelConfigEmbeddings(Embeddings):
    """按 ModelConfig 调用本地或 LiteLLM embedding。"""

    def __init__(self, model: ModelConfig) -> None:
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if invoke_mode_from_model(self._model) == INVOKE_MODE_LOCAL:
            return LocalEmbeddings(self._model.model_name).embed_documents(texts)
        return litellm_embed_texts(
            texts,
            model=resolve_litellm_model(self._model),
            api_key=self._model.api_key_encrypted,
            api_base=self._model.api_base,
        )

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embeddings(model: ModelConfig) -> Embeddings:
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
