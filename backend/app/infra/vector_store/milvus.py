"""
Milvus 向量库实现（``VectorStore`` 协议）。

设计要点
--------
- 使用 ``pymilvus.MilvusClient`` **直连** insert/search/delete，不经过 LangChain ORM。
  原因：langchain_milvus 在已有 collection 上用 ``Collection(using=alias)`` 时，
  alias 与全局 ``connections`` 池不一致会触发 ``ConnectionNotExistException``。
- 向量在 RAG pipeline 中已算好，**不使用** ``PrecomputedEmbeddings``，直接写 ``FLOAT_VECTOR``。
- 按 embedding **维度** 拆分 collection（``document_chunk_{dim}``），禁止不同维度混写同一表。
- 检索度量：L2 + AUTOINDEX；过滤表达式见 ``milvus_filter_expr``（tenant_id / kb_id）。

配置：``MILVUS_URI``、``MILVUS_TOKEN``、``MILVUS_DB_NAME``（见 Settings）。
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

# 与 langchain_milvus 默认 collection 命名习惯对齐，后缀为维度整数
COLLECTION_PREFIX = "document_chunk_"
PRIMARY_FIELD = "id"  # 主键，默认 chunk_id，可与 kb_vector_refs.vector_id 对应
VECTOR_FIELD = "vector"

# search 时拉回的标量字段（用于组装 retriever hit）
_SEARCH_OUTPUT_FIELDS = [
    TEXT_KEY,
    METADATA_CHUNK_ID,
    METADATA_DOCUMENT_ID,
    METADATA_TENANT_ID,
    METADATA_KB_ID,
]


def collection_name_for_dimension(dimension: int) -> str:
    """按 embedding 维度分 collection，避免混维写入。"""
    return f"{COLLECTION_PREFIX}{dimension}"


def _client_kwargs() -> dict[str, Any]:
    """从配置构造 MilvusClient 连接参数。"""
    settings = get_settings()
    kwargs: dict[str, Any] = {"uri": settings.milvus_uri}
    if settings.milvus_token:
        kwargs["token"] = settings.milvus_token
    if settings.milvus_db_name:
        kwargs["db_name"] = settings.milvus_db_name
    return kwargs


@lru_cache
def _client() -> MilvusClient:
    """进程内单例 MilvusClient（直连，不走 langchain ORM connections）。"""
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
    """列出 insert 必填标量字段（不含 vector）。"""
    desc = client.describe_collection(collection_name)
    return [
        f["name"]
        for f in desc["fields"]
        if f["name"] != VECTOR_FIELD
    ]


def _assert_row_matches_schema(
    client: MilvusClient, collection_name: str, row: dict[str, Any]
) -> None:
    """写入前校验行字段齐全，避免 Milvus 报缺 tenant_id 等。"""
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
        # 关闭 dynamic_field，字段集与 integrations.langchain.vector.documents 常量一致
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

    # 新 collection 或迁移后无索引时创建向量索引并 load（检索前必须 load）
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
    """将 MilvusClient.search 原始结果转为 LangChain Document + 距离。"""
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
    """
    Milvus 后端；业务经 ``app.rag.index.gateway`` 调用，不直接 import 本类。

    实现 ``VectorStore`` 协议全部方法；**无** ``search_hybrid``（混合检索走 PG 关键词 + RRF）。
    """

    def ensure_schema(self, dimension: int) -> None:
        """确保对应维度的 collection、索引已创建并 load。"""
        _ensure_collection(_client(), validate_dimension(dimension))

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        """插入一条分片向量，主键默认 chunk_id。"""
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
        """L2 近似检索，按 tenant_id / kb_id 过滤。"""
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
        """
        文档删除时清理向量。

        遍历 ``known_embedding_dimensions()`` 中配置的维度，避免漏删历史 collection。
        """
        client = _client()
        expr = f'{METADATA_DOCUMENT_ID} == "{document_id}"'
        for dim in known_embedding_dimensions():
            name = collection_name_for_dimension(dim)
            if client.has_collection(name):
                client.delete(collection_name=name, filter=expr)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """按主键 id 批量删除（与 upsert 时 PRIMARY_FIELD 一致）。"""
        if not chunk_ids:
            return
        client = _client()
        for dim in known_embedding_dimensions():
            name = collection_name_for_dimension(dim)
            if client.has_collection(name):
                client.delete(collection_name=name, ids=chunk_ids)

    def health_check(self) -> bool:
        """探测 Milvus 是否可连接。"""
        try:
            MilvusClient(**_client_kwargs()).list_collections()
            return True
        except Exception:
            return False
