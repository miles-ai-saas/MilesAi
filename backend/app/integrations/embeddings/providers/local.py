"""本地 Sentence-Transformers 向量化。"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.models.model import ModelConfig


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class LocalEmbeddings(Embeddings):
    """LangChain Embeddings 包装（供需要 Embeddings 接口的场景）。"""

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


class LocalEmbeddingProvider:
    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        return LocalEmbeddings(model.model_name).embed_documents(texts)
