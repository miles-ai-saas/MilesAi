"""LangChain Embeddings：本地 Sentence-Transformers 或 LiteLLM 云端 API。"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.core.config import Settings, get_settings

DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _sentence_transformer():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    model_name = settings.embedding_model_name or DEFAULT_LOCAL_MODEL
    return SentenceTransformer(model_name)


class LocalEmbeddings(Embeddings):
    """本地 Sentence-Transformers（默认，维度 384）。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = _sentence_transformer()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LiteLLMEmbeddings(Embeddings):
    """LiteLLM 统一 embedding API（需配置 API Key / 模型名）。"""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_litellm_model
        self._api_key = settings.embedding_litellm_api_key or None
        self._api_base = settings.embedding_litellm_api_base

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


@lru_cache
def get_embeddings() -> Embeddings:
    settings = get_settings()
    if settings.embedding_backend.strip().lower() == "litellm":
        return LiteLLMEmbeddings(settings)
    return LocalEmbeddings()


# 兼容旧名
PlatformEmbeddings = LocalEmbeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_embeddings().embed_documents(texts)


def embed_query(query: str) -> list[float]:
    return get_embeddings().embed_query(query)
