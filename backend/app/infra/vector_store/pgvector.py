"""PostgreSQL pgvector 实现（预留）。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infra.vector_store.base import ChunkVectorRecord


class PgVectorStore:
    """pgvector 后端：待实现（需在 PG 中建向量列与索引）。"""

    def ensure_schema(self, dimension: int) -> None:
        raise NotImplementedError(
            "VECTOR_STORE_BACKEND=pgvector 尚未实现，请使用 weaviate 或等待后续版本"
        )

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        raise NotImplementedError("pgvector upsert 尚未实现")

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("pgvector search 尚未实现")

    def delete_by_document(self, document_id: UUID) -> None:
        raise NotImplementedError("pgvector delete 尚未实现")

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        raise NotImplementedError("pgvector delete 尚未实现")

    def health_check(self) -> bool:
        return False
