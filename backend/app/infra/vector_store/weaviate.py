"""Weaviate 向量存储实现（默认后端）。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter, MetadataQuery

from app.core.config import Settings, get_settings
from app.utils.idgen import generate_uuid
from app.infra.vector_store.base import ChunkVectorRecord

CLASS_NAME = "DocumentChunk"


@lru_cache
def _get_weaviate_client() -> weaviate.WeaviateClient:
    s = get_settings()
    return weaviate.connect_to_custom(
        http_host=s.weaviate_host,
        http_port=s.weaviate_port,
        http_secure=s.weaviate_scheme == "https",
        grpc_host=s.weaviate_host,
        grpc_port=50051,
        grpc_secure=False,
        skip_init_checks=True,
    )


class WeaviateVectorStore:
    def __init__(self, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        self._host = s.weaviate_host
        self._port = s.weaviate_port
        self._scheme = s.weaviate_scheme

    def _client(self) -> weaviate.WeaviateClient:
        return _get_weaviate_client()

    def ensure_schema(self, dimension: int) -> None:
        client = self._client()
        if client.collections.exists(CLASS_NAME):
            return
        client.collections.create(
            name=CLASS_NAME,
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(distance_metric="cosine"),
            properties=[
                Property(name="tenant_id", data_type=DataType.TEXT),
                Property(name="kb_id", data_type=DataType.TEXT),
                Property(name="document_id", data_type=DataType.TEXT),
                Property(name="chunk_id", data_type=DataType.TEXT),
                Property(name="modality", data_type=DataType.TEXT),
                Property(name="content_preview", data_type=DataType.TEXT),
                Property(name="object_key", data_type=DataType.TEXT),
                Property(name="page_no", data_type=DataType.INT),
            ],
        )

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        self.ensure_schema(len(record.vector))
        collection = self._client().collections.get(CLASS_NAME)
        obj_id = record.external_id or str(generate_uuid())
        properties = {
            "tenant_id": str(record.tenant_id),
            "kb_id": str(record.kb_id),
            "document_id": str(record.document_id),
            "chunk_id": str(record.chunk_id),
            "modality": "text",
            "content_preview": record.content_preview[:500],
            "object_key": record.object_key,
            "page_no": record.page_no or 0,
        }
        collection.data.insert(
            properties=properties, vector=record.vector, uuid=obj_id
        )
        return obj_id

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.ensure_schema(len(query_vector))
        collection = self._client().collections.get(CLASS_NAME)
        filters = Filter.by_property("tenant_id").equal(str(tenant_id))
        if kb_id:
            filters = filters & Filter.by_property("kb_id").equal(str(kb_id))
        result = collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(distance=True),
        )
        hits: list[dict[str, Any]] = []
        for obj in result.objects:
            props = obj.properties or {}
            distance = obj.metadata.distance if obj.metadata else None
            hits.append(
                {
                    "vector_id": str(obj.uuid),
                    "chunk_id": props.get("chunk_id"),
                    "document_id": props.get("document_id"),
                    "content_preview": props.get("content_preview"),
                    "score": 1 - (distance or 0),
                }
            )
        return hits

    def search_hybrid(
        self,
        query: str,
        *,
        query_vector: list[float],
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
        alpha: float = 0.5,
    ) -> list[dict[str, Any]]:
        """向量 + BM25 混合检索（alpha：1=纯向量，0=纯关键词）。"""
        self.ensure_schema(len(query_vector))
        collection = self._client().collections.get(CLASS_NAME)
        filters = Filter.by_property("tenant_id").equal(str(tenant_id))
        if kb_id:
            filters = filters & Filter.by_property("kb_id").equal(str(kb_id))
        result = collection.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=max(0.0, min(1.0, alpha)),
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(score=True),
        )
        hits: list[dict[str, Any]] = []
        for obj in result.objects:
            props = obj.properties or {}
            score = float(obj.metadata.score) if obj.metadata and obj.metadata.score else 0.0
            hits.append(
                {
                    "vector_id": str(obj.uuid),
                    "chunk_id": props.get("chunk_id"),
                    "document_id": props.get("document_id"),
                    "content_preview": props.get("content_preview"),
                    "score": score,
                    "score_vector": score,
                    "score_keyword": None,
                }
            )
        return hits

    def delete_by_document(self, document_id: UUID) -> None:
        client = self._client()
        if not client.collections.exists(CLASS_NAME):
            return
        collection = client.collections.get(CLASS_NAME)
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(str(document_id))
        )

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        client = self._client()
        if not client.collections.exists(CLASS_NAME):
            return
        collection = client.collections.get(CLASS_NAME)
        for cid in chunk_ids:
            try:
                collection.data.delete_by_id(cid)
            except Exception:
                pass

    def health_check(self) -> bool:
        import httpx

        scheme = "https" if self._scheme == "https" else "http"
        url = f"{scheme}://{self._host}:{self._port}/v1/.well-known/ready"
        try:
            with httpx.Client(timeout=3.0) as client:
                r = client.get(url)
                return r.status_code == 200
        except Exception:
            return False
