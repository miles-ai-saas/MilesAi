"""向量存储抽象（L4）。

业务代码请经 miles_ai.rag.index.gateway 读写，勿直接依赖具体 Milvus/pgvector 实现。

单条 ``upsert_chunk`` 的实现可委托 ``upsert_chunks([record])[0]``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class ChunkVectorRecord:
    """
    写入向量库的一条分片记录（由 RAG gateway / ingest 构造）。

    vector 已在 pipeline 中算好；各后端负责落库与元数据过滤检索。
    external_id 可选，默认与 chunk_id 一致，写入 Milvus/pgvector 主键。
    """

    vector: list[float]  # 分片 embedding 向量
    tenant_id: UUID  # 租户 ID
    kb_id: UUID  # 知识库 ID
    document_id: UUID  # 文档 ID
    chunk_id: UUID  # PG 分片主键
    content_preview: str  # 写入向量库文本字段，通常截断预览
    object_key: str  # 对象存储 key，便于回溯原文
    page_no: int | None = None  # 页码（1-based，可选）
    external_id: str | None = None  # 向量库主键；默认与 chunk_id 一致


def validate_dimension(dimension: int) -> int:
    """校验向量维度为正整数。"""
    if dimension <= 0:
        raise ValueError(f"无效的向量维度: {dimension}")
    return dimension


@runtime_checkable
class VectorStore(Protocol):
    """向量检索后端：默认 Weaviate，可扩展 pgvector / Milvus。"""

    def ensure_schema(self, dimension: int) -> None:
        """确保 collection/schema 存在且维度匹配（幂等）。"""
        ...

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        """返回外部向量 ID（写入 PG `kb_vector_refs`）。"""
        ...

    def upsert_chunks(self, records: list[ChunkVectorRecord]) -> list[str]:
        """批量写入；返回与 records 等长的 external id 列表。空列表返回 []。"""
        ...

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """按查询向量做租户隔离的相似度检索，返回命中 chunk 元数据与分数。"""
        ...

    def delete_by_document(self, document_id: UUID) -> None:
        """删除某文档的全部向量。"""
        ...

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """按外部向量 ID 批量删除。"""
        ...

    def health_check(self) -> bool:
        """探测向量后端连通性。"""
        ...
