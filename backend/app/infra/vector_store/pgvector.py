"""pgvector（langchain_community.PGVector）。

与 Milvus 共用 ChunkVectorRecord / gateway 门面；按维度分 collection。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from app.integrations.langchain.vector.documents import (
    distance_pairs_to_hits,
    pg_metadata_filter,
)
from app.infra.vector_store.langchain_base import foreach_dimension, upsert_add_embeddings
from app.infra.vector_store.precomputed import PrecomputedEmbeddings

COLLECTION_PREFIX = "milesai_kb_"


def collection_name_for_dimension(dimension: int) -> str:
    """按 embedding 维度命名 PGVector collection。"""
    return f"{COLLECTION_PREFIX}{dimension}"


class PgVectorStore:
    """PostgreSQL pgvector 向量库实现。"""

    @staticmethod
    @lru_cache
    def _store(dimension: int):
        """按维度缓存 PGVector 实例。"""
        from langchain_community.vectorstores import PGVector

        return PGVector(
            connection_string=get_settings().database_url_sync,
            embedding_function=PrecomputedEmbeddings(),
            collection_name=collection_name_for_dimension(dimension),
            embedding_length=dimension,
            use_jsonb=True,
            create_extension=True,
        )

    def ensure_schema(self, dimension: int) -> None:
        """触发 PGVector 建表/扩展（幂等）。"""
        self._store(validate_dimension(dimension))

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        """写入预计算向量与元数据，返回 external id。"""
        dim = validate_dimension(len(record.vector))
        self.ensure_schema(dim)
        return upsert_add_embeddings(self._store(dim), record)

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """向量相似度检索，JSONB 元数据过滤 tenant/kb。"""
        dim = validate_dimension(len(query_vector))
        self.ensure_schema(dim)
        pairs = self._store(dim).similarity_search_with_score_by_vector(
            embedding=query_vector,
            k=limit,
            filter=pg_metadata_filter(tenant_id, kb_id),
        )
        return distance_pairs_to_hits(pairs)

    def delete_by_document(self, document_id: UUID) -> None:
        """按 cmetadata.document_id 删除所有维度 collection 中的行。"""
        from sqlalchemy import create_engine, text

        sql = text(
            "DELETE FROM langchain_pg_embedding AS e "
            "USING langchain_pg_collection AS c "
            "WHERE e.collection_id = c.uuid "
            "AND c.name LIKE :prefix "
            "AND e.cmetadata->>'document_id' = :doc_id"
        )
        with create_engine(get_settings().database_url_sync).connect() as conn:
            conn.execute(
                sql,
                {"prefix": f"{COLLECTION_PREFIX}%", "doc_id": str(document_id)},
            )
            conn.commit()

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """按 LangChain embedding 主键批量删除。"""
        if not chunk_ids:
            return

        def _delete(store: Any) -> None:
            store.delete(ids=chunk_ids, collection_only=True)

        foreach_dimension(self._store, _delete)

    def health_check(self) -> bool:
        """探测同步库连接是否可用。"""
        try:
            from sqlalchemy import create_engine, text

            with create_engine(get_settings().database_url_sync).connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
