"""Weaviate 向量存储封装。"""

from functools import lru_cache
from typing import Any
from uuid import UUID

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter, MetadataQuery

from app.common.exceptions import AppError
from app.core.config import get_settings
from app.utils.idgen import generate_uuid

CLASS_NAME = "DocumentChunk"
settings = get_settings()


@lru_cache
def get_weaviate_client() -> weaviate.WeaviateClient:
    return weaviate.connect_to_custom(
        http_host=settings.weaviate_host,
        http_port=settings.weaviate_port,
        http_secure=settings.weaviate_scheme == "https",
        grpc_host=settings.weaviate_host,
        grpc_port=50051,
        grpc_secure=False,
        skip_init_checks=True,
    )


def ensure_schema(dimension: int = 384) -> None:
    client = get_weaviate_client()
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
            Property(name="minio_key", data_type=DataType.TEXT),
            Property(name="page_no", data_type=DataType.INT),
        ],
    )


def upsert_chunk_vector(
    *,
    vector: list[float],
    tenant_id: UUID,
    kb_id: UUID,
    document_id: UUID,
    chunk_id: UUID,
    content_preview: str,
    minio_key: str,
    page_no: int | None = None,
    weaviate_uuid: str | None = None,
) -> str:
    ensure_schema(len(vector))
    client = get_weaviate_client()
    collection = client.collections.get(CLASS_NAME)
    obj_id = weaviate_uuid or str(generate_uuid())
    properties = {
        "tenant_id": str(tenant_id),
        "kb_id": str(kb_id),
        "document_id": str(document_id),
        "chunk_id": str(chunk_id),
        "modality": "text",
        "content_preview": content_preview[:500],
        "minio_key": minio_key,
        "page_no": page_no or 0,
    }
    collection.data.insert(properties=properties, vector=vector, uuid=obj_id)
    return obj_id


def search_vectors(
    query_vector: list[float],
    *,
    tenant_id: UUID,
    kb_id: UUID | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ensure_schema(len(query_vector))
    client = get_weaviate_client()
    collection = client.collections.get(CLASS_NAME)
    filters = Filter.by_property("tenant_id").equal(str(tenant_id))
    if kb_id:
        filters = filters & Filter.by_property("kb_id").equal(str(kb_id))
    result = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        filters=filters,
        return_metadata=MetadataQuery(distance=True),
    )
    hits = []
    for obj in result.objects:
        props = obj.properties or {}
        distance = obj.metadata.distance if obj.metadata else None
        hits.append(
            {
                "weaviate_uuid": str(obj.uuid),
                "chunk_id": props.get("chunk_id"),
                "document_id": props.get("document_id"),
                "content_preview": props.get("content_preview"),
                "score": 1 - (distance or 0),
            }
        )
    return hits


def delete_by_document(document_id: UUID) -> None:
    client = get_weaviate_client()
    if not client.collections.exists(CLASS_NAME):
        return
    collection = client.collections.get(CLASS_NAME)
    collection.data.delete_many(
        where=Filter.by_property("document_id").equal(str(document_id))
    )


def delete_by_chunk_ids(chunk_ids: list[str]) -> None:
    if not chunk_ids:
        return
    client = get_weaviate_client()
    if not client.collections.exists(CLASS_NAME):
        return
    collection = client.collections.get(CLASS_NAME)
    for cid in chunk_ids:
        try:
            collection.data.delete_by_id(cid)
        except Exception:
            pass
