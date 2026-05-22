"""预计算向量 Embeddings（供 LangChain VectorStore 写入/检索时注入向量）。"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings


class PrecomputedEmbeddings(Embeddings):
    """将已算好的向量交给 LangChain ``add_texts`` / ``similarity_search`` 使用。"""

    def __init__(
        self,
        vectors: list[list[float]] | None = None,
        *,
        query_vector: list[float] | None = None,
    ) -> None:
        self._vectors = vectors or []
        self._query_vector = query_vector

    def with_batch(self, vectors: list[list[float]]) -> PrecomputedEmbeddings:
        return PrecomputedEmbeddings(vectors, query_vector=self._query_vector)

    def with_query(self, query_vector: list[float]) -> PrecomputedEmbeddings:
        return PrecomputedEmbeddings(self._vectors, query_vector=query_vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if len(self._vectors) != len(texts):
            raise ValueError(
                f"预计算向量条数({len(self._vectors)})与文本条数({len(texts)})不一致"
            )
        return self._vectors

    def embed_query(self, text: str) -> list[float]:
        if self._query_vector is None:
            raise ValueError("未设置 query_vector，无法 embed_query")
        return self._query_vector
