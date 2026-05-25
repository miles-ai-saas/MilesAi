"""
预计算向量 Embeddings 适配器（LangChain Embeddings 接口）。

背景
----
RAG 入库在 ``app.rag.pipeline`` 中已调用租户配置的 embedding 模型得到 ``list[float]``；
写入 Weaviate / pgvector 时若再传真实 Embedding 模型，LangChain 会对同一段文本重复计费请求。

本类实现 LangChain ``Embeddings`` 协议，但 **不发起网络请求**：
- ``embed_documents``：返回构造时绑定的批量向量（与 texts 一一对应）
- ``embed_query``：返回构造时绑定的 query 向量（忽略传入的 query 文本）

使用方
------
- **pgvector**：``PGVector(embedding_function=PrecomputedEmbeddings())``，写入走 ``add_embeddings``
- **Weaviate**：检索前临时 ``store._embedding = PrecomputedEmbeddings(query_vector=...)``
- **Milvus**：**不经过本类**，``MilvusVectorStore.upsert_chunk`` 直接 ``insert`` FLOAT_VECTOR

与 ``integrations.embeddings`` 的分工：后者在 pipeline 中**算向量**；本类仅**传递**已算向量以满足 LangChain API。
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings


class PrecomputedEmbeddings(Embeddings):
    """
    将 pipeline 已算好的向量注入 LangChain VectorStore API。

    不可变式配置：通过 ``with_batch`` / ``with_query`` 派生新实例，避免并发写共享状态。
    """

    def __init__(
        self,
        vectors: list[list[float]] | None = None,
        *,
        query_vector: list[float] | None = None,
    ) -> None:
        # vectors：add_texts / add_embeddings 批量写入路径
        self._vectors = vectors or []
        # query_vector：similarity_search_by_vector 或 Weaviate 检索前注入
        self._query_vector = query_vector

    def with_batch(self, vectors: list[list[float]]) -> PrecomputedEmbeddings:
        """绑定本批 upsert 向量，供 ``embed_documents`` 与 texts 对齐返回。"""
        return PrecomputedEmbeddings(vectors, query_vector=self._query_vector)

    def with_query(self, query_vector: list[float]) -> PrecomputedEmbeddings:
        """绑定检索 query 向量，供 ``embed_query`` 在 LangChain 检索链中使用。"""
        return PrecomputedEmbeddings(self._vectors, query_vector=query_vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        LangChain 写入时调用；条数必须与 texts 相同。

        texts 内容仅用于满足 API 形状，实际向量以 ``_vectors`` 为准。
        """
        if len(self._vectors) != len(texts):
            raise ValueError(
                f"预计算向量条数({len(self._vectors)})与文本条数({len(texts)})不一致"
            )
        return self._vectors

    def embed_query(self, text: str) -> list[float]:
        """
        LangChain 部分检索 API 会先 embed_query；此处直接返回预置向量。

        参数 text 被忽略，调用方须事先 ``with_query`` 绑定 query 向量。
        """
        if self._query_vector is None:
            raise ValueError("未设置 query_vector，无法 embed_query")
        return self._query_vector
