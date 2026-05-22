"""LangChain Embeddings：按知识库绑定的向量化规格调用。"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from langchain_core.embeddings import Embeddings

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from app.models.kb import KnowledgeBase

DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class LocalEmbeddings(Embeddings):
    """本地 Sentence-Transformers。"""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    @lru_cache(maxsize=4)
    def _model(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoder = self._model(self._model_name)
        vectors = encoder.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LiteLLMEmbeddings(Embeddings):
    """LiteLLM 云端 embedding。"""

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._model = model_name
        self._api_key = api_key
        self._api_base = api_base

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from app.ai_stack.litellm.adapter import litellm_embed_texts

        return litellm_embed_texts(
            texts,
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
        )

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def _litellm_credentials(settings: Settings) -> tuple[str | None, str | None]:
    key = settings.embedding_litellm_api_key or None
    base = settings.embedding_litellm_api_base
    return key, base


def get_embeddings_for_kb(kb: KnowledgeBase) -> Embeddings:
    """按知识库固化规格返回 Embeddings 实例。"""
    backend = (kb.embedding_backend or "local").strip().lower()
    model_name = kb.embedding_model_name or DEFAULT_LOCAL_MODEL
    if backend == "litellm":
        settings = get_settings()
        api_key, api_base = _litellm_credentials(settings)
        return LiteLLMEmbeddings(model_name, api_key=api_key, api_base=api_base)
    return LocalEmbeddings(model_name)


@lru_cache
def get_embeddings() -> Embeddings:
    """全局默认（无 KB 上下文时的兜底）。"""
    settings = get_settings()
    if settings.embedding_backend.strip().lower() == "litellm":
        key, base = _litellm_credentials(settings)
        return LiteLLMEmbeddings(
            settings.embedding_litellm_model,
            api_key=key,
            api_base=base,
        )
    return LocalEmbeddings(settings.embedding_model_name or DEFAULT_LOCAL_MODEL)


PlatformEmbeddings = LocalEmbeddings


def embed_texts_for_kb(kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    return get_embeddings_for_kb(kb).embed_documents(texts)


def embed_query_for_kb(kb: KnowledgeBase, query: str) -> list[float]:
    return get_embeddings_for_kb(kb).embed_query(query)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_embeddings().embed_documents(texts)


def embed_query(query: str) -> list[float]:
    return get_embeddings().embed_query(query)
