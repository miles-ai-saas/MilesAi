"""预计算向量 Embeddings（供 LangChain VectorStore 写入/检索时注入向量）。

入库已在 pipeline 中调用远程 embedding；pgvector/Weaviate/Milvus 写入时
不把文本再送模型，而是通过本类把已有 vector 交给 LangChain store API。
"""

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
        """vectors：批量写入；query_vector：检索时注入 query 向量。"""
        self._vectors = vectors or []
        self._query_vector = query_vector

    def with_batch(self, vectors: list[list[float]]) -> PrecomputedEmbeddings:
        """绑定本批 upsert 的向量（add_texts 路径）。"""
        return PrecomputedEmbeddings(vectors, query_vector=self._query_vector)

    def with_query(self, query_vector: list[float]) -> PrecomputedEmbeddings:
        """绑定检索 query 向量（similarity_search / hybrid 路径）。"""
        return PrecomputedEmbeddings(self._vectors, query_vector=query_vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """返回预置向量，条数须与 texts 一致。"""
        if len(self._vectors) != len(texts):
            raise ValueError(
                f"预计算向量条数({len(self._vectors)})与文本条数({len(texts)})不一致"
            )
        return self._vectors

    def embed_query(self, text: str) -> list[float]:
        """返回预置 query 向量，忽略 text 内容。"""
        if self._query_vector is None:
            raise ValueError("未设置 query_vector，无法 embed_query")
        return self._query_vector
