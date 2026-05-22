"""Milvus（langchain_community.Milvus）。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from app.integrations.langchain.vector.documents import distance_pairs_to_hits, milvus_filter_expr
from app.infra.vector_store.langchain_base import foreach_dimension, upsert_add_texts
from app.infra.vector_store.precomputed import PrecomputedEmbeddings

COLLECTION_PREFIX = "document_chunk_"


def collection_name_for_dimension(dimension: int) -> str:
    return f"{COLLECTION_PREFIX}{dimension}"


class MilvusVectorStore:
    @staticmethod
    @lru_cache
    def _store(dimension: int):
        from langchain_community.vectorstores import Milvus

        settings = get_settings()
        connection_args: dict[str, Any] = {"uri": settings.milvus_uri}
        if settings.milvus_token:
            connection_args["token"] = settings.milvus_token
        return Milvus(
            embedding_function=PrecomputedEmbeddings(),
            collection_name=collection_name_for_dimension(dimension),
            connection_args=connection_args,
            primary_field="id",
            text_field="content_preview",
            vector_field="vector",
            auto_id=False,
        )

    def ensure_schema(self, dimension: int) -> None:
        self._store(validate_dimension(dimension))

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        dim = validate_dimension(len(record.vector))
        self.ensure_schema(dim)
        return upsert_add_texts(
            self._store(dim), record, embedding_attr="embedding_function"
        )

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        dim = validate_dimension(len(query_vector))
        self.ensure_schema(dim)
        pairs = self._store(dim).similarity_search_with_score_by_vector(
            embedding=query_vector,
            k=limit,
            expr=milvus_filter_expr(tenant_id, kb_id),
        )
        return distance_pairs_to_hits(pairs)

    def delete_by_document(self, document_id: UUID) -> None:
        expr = f'document_id == "{document_id}"'

        def _delete(store: Any) -> None:
            if store.col is not None:
                store.delete(expr=expr)

        foreach_dimension(self._store, _delete)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return

        def _delete(store: Any) -> None:
            if store.col is not None:
                store.delete(ids=chunk_ids)

        foreach_dimension(self._store, _delete)

    def health_check(self) -> bool:
        try:
            from pymilvus import MilvusClient

            settings = get_settings()
            kwargs: dict[str, Any] = {"uri": settings.milvus_uri}
            if settings.milvus_token:
                kwargs["token"] = settings.milvus_token
            MilvusClient(**kwargs).list_collections()
            return True
        except Exception:
            return False
