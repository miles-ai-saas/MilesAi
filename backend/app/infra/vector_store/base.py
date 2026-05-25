"""向量存储抽象（L4）。

业务代码请经 app.rag.index.gateway 读写，勿直接依赖具体 Milvus/pgvector 实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class ChunkVectorRecord:
    """写入向量库的一条分片记录。"""

    vector: list[float]
    tenant_id: UUID
    kb_id: UUID
    document_id: UUID
    chunk_id: UUID
    content_preview: str
    object_key: str
    page_no: int | None = None
    external_id: str | None = None


def validate_dimension(dimension: int) -> int:
    """校验向量维度为正整数。"""
    if dimension <= 0:
        raise ValueError(f"无效的向量维度: {dimension}")
    return dimension


@runtime_checkable
class VectorStore(Protocol):
    """向量检索后端：默认 Weaviate，可扩展 pgvector / Milvus。"""

    def ensure_schema(self, dimension: int) -> None: ...

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        """返回外部向量 ID（写入 PG `kb_vector_refs`）。"""
        ...

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]: ...

    def delete_by_document(self, document_id: UUID) -> None: ...

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None: ...

    def health_check(self) -> bool: ...
