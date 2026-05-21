"""LangChain Embeddings 适配：底层仍为 Sentence-Transformers。"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.core.config import get_settings

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _sentence_transformer():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    model_name = getattr(settings, "embedding_model_name", None) or DEFAULT_MODEL
    return SentenceTransformer(model_name)


class PlatformEmbeddings(Embeddings):
    """统一向量入口，实现 LangChain Embeddings 接口。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = _sentence_transformer()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


_default_embeddings = PlatformEmbeddings()


def get_embeddings() -> PlatformEmbeddings:
    return _default_embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _default_embeddings.embed_documents(texts)


def embed_query(query: str) -> list[float]:
    return _default_embeddings.embed_query(query)
