"""
向量化运行时：ModelConfig → LangChain ``Embeddings`` 门面。

调用链
------
``embed_*_for_kb`` → ``resolve_embedding_model_*`` → ``build_embeddings``
→ ``ModelConfigEmbeddings`` → ``registry.embed_texts_for_model`` → 具体 Provider。

与 ``PrecomputedEmbeddings`` 的分工
----------------------------------
本模块负责**真实 API 调用**（入库分片、检索 query）；
向量库写入阶段使用 ``infra.vector_store.precomputed``，避免 LangChain 二次 embed。
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
    """按 ``ModelConfig.extra.invoke_mode`` 经 registry 分发到 OpenAI 兼容 / LiteLLM / Local。"""

    def __init__(self, model: ModelConfig) -> None:
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化（``run_ingest_pipeline`` 注入路径）。"""
        return embed_texts_for_model(self._model, texts)

    def embed_query(self, text: str) -> list[float]:
        """单条 query（检索 API / Agent）；实现为单条 batch embed。"""
        return self.embed_documents([text])[0]


def build_embeddings(model: ModelConfig) -> Embeddings:
    """校验 model_type=embedding 后返回可注入 LangChain 的 Embeddings 实例。"""
    ensure_embedding_model_type(model)
    return ModelConfigEmbeddings(model)


def merge_effective_embedding_model(
    model: ModelConfig,
    *,
    api_base: str | None = None,
    api_key_encrypted: str | None = None,
) -> ModelConfig:
    """合并租户 BYOK 后的 ModelConfig 副本（不修改 ORM 原行）。"""
    effective = copy(model)
    if api_base:
        effective.api_base = api_base
    if api_key_encrypted:
        effective.api_key_encrypted = api_key_encrypted
    return effective
