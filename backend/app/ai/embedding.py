"""文本向量化（Sentence-Transformers）。"""

from functools import lru_cache

from app.core.config import get_settings

settings = get_settings()
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _get_model():
    from sentence_transformers import SentenceTransformer

    model_name = getattr(settings, "embedding_model_name", None) or DEFAULT_MODEL
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
