"""Milvus（MilvusClient 直连，与 LangChain 建表 schema 兼容）。

避免 langchain_milvus 在已有 collection 上通过 ORM ``Collection(using=alias)``
访问索引，alias 与 ``connections`` 池不一致时会触发 ``ConnectionNotExistException``。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from pymilvus import DataType, MilvusClient

from app.core.config import get_settings
from app.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from app.common.exceptions import AppError
from app.integrations.langchain.vector.documents import (
    METADATA_CHUNK_ID,
    METADATA_DOCUMENT_ID,
    METADATA_KB_ID,
    METADATA_MODALITY,
    METADATA_OBJECT_KEY,
    METADATA_PAGE_NO,
    METADATA_TENANT_ID,
    TEXT_KEY,
    distance_pairs_to_hits,
    milvus_filter_expr,
    known_embedding_dimensions,
)
from langchain_core.documents import Document

COLLECTION_PREFIX = "document_chunk_"
PRIMARY_FIELD = "id"
VECTOR_FIELD = "vector"

_SEARCH_OUTPUT_FIELDS = [
    TEXT_KEY,
    METADATA_CHUNK_ID,
    METADATA_DOCUMENT_ID,
    METADATA_TENANT_ID,
    METADATA_KB_ID,
]


def collection_name_for_dimension(dimension: int) -> str:
    return f"{COLLECTION_PREFIX}{dimension}"


def _client_kwargs() -> dict[str, Any]:
    settings = get_settings()
    kwargs: dict[str, Any] = {"uri": settings.milvus_uri}
    if settings.milvus_token:
        kwargs["token"] = settings.milvus_token
    if settings.milvus_db_name:
        kwargs["db_name"] = settings.milvus_db_name
    return kwargs


@lru_cache
def _client() -> MilvusClient:
    return MilvusClient(**_client_kwargs())


def _record_to_row(record: ChunkVectorRecord) -> dict[str, Any]:
    """按 collection 固定 schema 构造行（勿依赖 LangChain Document 再 merge）。"""
    chunk_id = str(record.chunk_id)
    return {
        PRIMARY_FIELD: str(record.external_id or chunk_id),
        TEXT_KEY: (record.content_preview or "")[:500],
        VECTOR_FIELD: list(record.vector),
        METADATA_TENANT_ID: str(record.tenant_id),
        METADATA_KB_ID: str(record.kb_id),
        METADATA_DOCUMENT_ID: str(record.document_id),
        METADATA_CHUNK_ID: chunk_id,
        METADATA_OBJECT_KEY: record.object_key or "",
        METADATA_PAGE_NO: int(record.page_no if record.page_no is not None else 0),
        METADATA_MODALITY: "text",
    }


def _required_insert_fields(client: MilvusClient, collection_name: str) -> list[str]:
    desc = client.describe_collection(collection_name)
    return [
        f["name"]
        for f in desc["fields"]
        if f["name"] != VECTOR_FIELD
    ]


def _assert_row_matches_schema(
    client: MilvusClient, collection_name: str, row: dict[str, Any]
) -> None:
    missing = [
        name
        for name in _required_insert_fields(client, collection_name)
        if name not in row or row[name] is None
    ]
    if missing:
        raise AppError(
            f"Milvus 写入缺少必填字段: {missing}",
            status_code=500,
        )


def _ensure_collection(client: MilvusClient, dimension: int) -> str:
    """确保 collection 存在、已建索引并 load（与 langchain_milvus 字段一致）。"""
    name = collection_name_for_dimension(dimension)
    if not client.has_collection(name):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name=TEXT_KEY,
            datatype=DataType.VARCHAR,
            max_length=65535,
        )
        schema.add_field(
            field_name=PRIMARY_FIELD,
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=65535,
        )
        schema.add_field(
            field_name=VECTOR_FIELD,
            datatype=DataType.FLOAT_VECTOR,
            dim=dimension,
        )
        for field_name in (
            METADATA_TENANT_ID,
            METADATA_KB_ID,
            METADATA_DOCUMENT_ID,
            METADATA_CHUNK_ID,
            METADATA_OBJECT_KEY,
            METADATA_MODALITY,
        ):
            schema.add_field(
                field_name=field_name,
                datatype=DataType.VARCHAR,
                max_length=65535,
            )
        schema.add_field(field_name=METADATA_PAGE_NO, datatype=DataType.INT64)

        client.create_collection(collection_name=name, schema=schema)

    if not client.list_indexes(name):
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name=VECTOR_FIELD,
            metric_type="L2",
            index_type="AUTOINDEX",
        )
        client.create_index(collection_name=name, index_params=index_params)

    client.load_collection(collection_name=name)
    return name


def _search_hit_rows(raw: list[list[dict[str, Any]]]) -> list[tuple[Document, float]]:
    pairs: list[tuple[Document, float]] = []
    for batch in raw:
        for hit in batch:
            entity = hit.get("entity") or hit
            distance = float(hit.get("distance", 0.0))
            doc = Document(
                page_content=str(entity.get(TEXT_KEY) or ""),
                metadata={
                    METADATA_CHUNK_ID: entity.get(METADATA_CHUNK_ID),
                    METADATA_DOCUMENT_ID: entity.get(METADATA_DOCUMENT_ID),
                    METADATA_TENANT_ID: entity.get(METADATA_TENANT_ID),
                    METADATA_KB_ID: entity.get(METADATA_KB_ID),
                },
                id=str(entity.get(PRIMARY_FIELD) or entity.get(METADATA_CHUNK_ID) or ""),
            )
            pairs.append((doc, distance))
    return pairs


class MilvusVectorStore:
    def ensure_schema(self, dimension: int) -> None:
        _ensure_collection(_client(), validate_dimension(dimension))

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        client = _client()
        dim = validate_dimension(len(record.vector))
        name = _ensure_collection(client, dim)
        row = _record_to_row(record)
        _assert_row_matches_schema(client, name, row)
        res = client.insert(collection_name=name, data=[row])
        ids = res.get("ids") or []
        return str(ids[0]) if ids else str(row[PRIMARY_FIELD])

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        client = _client()
        dim = validate_dimension(len(query_vector))
        name = _ensure_collection(client, dim)
        raw = client.search(
            collection_name=name,
            data=[query_vector],
            filter=milvus_filter_expr(tenant_id, kb_id),
            limit=limit,
            output_fields=_SEARCH_OUTPUT_FIELDS,
        )
        return distance_pairs_to_hits(_search_hit_rows(raw))

    def delete_by_document(self, document_id: UUID) -> None:
        client = _client()
        expr = f'{METADATA_DOCUMENT_ID} == "{document_id}"'
        for dim in known_embedding_dimensions():
            name = collection_name_for_dimension(dim)
            if client.has_collection(name):
                client.delete(collection_name=name, filter=expr)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        client = _client()
        for dim in known_embedding_dimensions():
            name = collection_name_for_dimension(dim)
            if client.has_collection(name):
                client.delete(collection_name=name, ids=chunk_ids)

    def health_check(self) -> bool:
        try:
            MilvusClient(**_client_kwargs()).list_collections()
            return True
        except Exception:
            return False
