"""Milvus 向量存储实现。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.utils.idgen import generate_uuid
from app.infra.vector_store.base import ChunkVectorRecord

COLLECTION_PREFIX = "document_chunk_"


def collection_name_for_dimension(dimension: int) -> str:
    """按向量维度分 Collection（与 Weaviate 单表不同，Milvus 维度在建表时固定）。"""
    return f"{COLLECTION_PREFIX}{dimension}"


@lru_cache
def _get_milvus_client():
    from pymilvus import MilvusClient

    s = get_settings()
    kwargs: dict[str, Any] = {"uri": s.milvus_uri}
    if s.milvus_token:
        kwargs["token"] = s.milvus_token
    if s.milvus_db_name and s.milvus_db_name != "default":
        kwargs["db_name"] = s.milvus_db_name
    return MilvusClient(**kwargs)


class MilvusVectorStore:
    """Milvus 2.x（MilvusClient）：按维度分 Collection，COSINE 检索。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _client(self):
        return _get_milvus_client()

    def _chunk_collections(self) -> list[str]:
        return [
            name
            for name in self._client().list_collections()
            if name.startswith(COLLECTION_PREFIX)
        ]

    def ensure_schema(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError(f"无效的向量维度: {dimension}")
        name = collection_name_for_dimension(dimension)
        client = self._client()
        if client.has_collection(name):
            return
        client.create_collection(
            collection_name=name,
            dimension=dimension,
            metric_type="COSINE",
            id_type="string",
            max_length=64,
            auto_id=False,
        )

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        dim = len(record.vector)
        self.ensure_schema(dim)
        collection = collection_name_for_dimension(dim)
        obj_id = record.external_id or str(generate_uuid())
        row = {
            "id": obj_id,
            "vector": record.vector,
            "tenant_id": str(record.tenant_id),
            "kb_id": str(record.kb_id),
            "document_id": str(record.document_id),
            "chunk_id": str(record.chunk_id),
            "content_preview": record.content_preview[:500],
            "object_key": record.object_key,
            "page_no": record.page_no or 0,
        }
        self._client().upsert(collection_name=collection, data=[row])
        return obj_id

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        dim = len(query_vector)
        self.ensure_schema(dim)
        collection = collection_name_for_dimension(dim)
        expr = f'tenant_id == "{tenant_id}"'
        if kb_id:
            expr += f' and kb_id == "{kb_id}"'

        results = self._client().search(
            collection_name=collection,
            data=[query_vector],
            filter=expr,
            limit=limit,
            output_fields=[
                "chunk_id",
                "document_id",
                "content_preview",
            ],
        )
        hits: list[dict[str, Any]] = []
        for batch in results or []:
            for item in batch:
                entity = item.get("entity") or {}
                distance = float(item.get("distance") or 0)
                hits.append(
                    {
                        "vector_id": str(item.get("id", "")),
                        "chunk_id": entity.get("chunk_id"),
                        "document_id": entity.get("document_id"),
                        "content_preview": entity.get("content_preview"),
                        "score": 1 - distance,
                    }
                )
        return hits

    def delete_by_document(self, document_id: UUID) -> None:
        doc_filter = f'document_id == "{document_id}"'
        client = self._client()
        for collection in self._chunk_collections():
            try:
                client.delete(collection_name=collection, filter=doc_filter)
            except Exception:
                pass

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """按向量库主键 ID 删除（与 `kb_vector_refs.vector_id` 一致）。"""
        if not chunk_ids:
            return
        client = self._client()
        for collection in self._chunk_collections():
            try:
                client.delete(collection_name=collection, ids=chunk_ids)
            except Exception:
                pass

    def health_check(self) -> bool:
        try:
            self._client().list_collections()
            return True
        except Exception:
            return False
