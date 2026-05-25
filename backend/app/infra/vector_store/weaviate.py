"""Weaviate（langchain-weaviate）。

支持原生 hybrid（BM25 + 向量）；VECTOR_STORE_BACKEND=weaviate 时检索可走 search_hybrid。
向量由 PrecomputedEmbeddings 注入，不在 Weaviate 侧再调 embedding API。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.query import Filter

from app.core.config import Settings, get_settings
from app.infra.vector_store.base import ChunkVectorRecord, validate_dimension
from app.integrations.langchain.vector.documents import (
    METADATA_CHUNK_ID,
    METADATA_DOCUMENT_ID,
    METADATA_KB_ID,
    METADATA_MODALITY,
    METADATA_OBJECT_KEY,
    METADATA_PAGE_NO,
    METADATA_TENANT_ID,
    TEXT_KEY,
    scored_pairs_to_hits,
)
from app.infra.vector_store.langchain_base import upsert_add_texts
from app.infra.vector_store.precomputed import PrecomputedEmbeddings

CLASS_NAME = "DocumentChunk"

_LC_ATTRS = (
    METADATA_TENANT_ID,
    METADATA_KB_ID,
    METADATA_DOCUMENT_ID,
    METADATA_CHUNK_ID,
    METADATA_MODALITY,
    METADATA_OBJECT_KEY,
    METADATA_PAGE_NO,
)


@lru_cache
def _client() -> weaviate.WeaviateClient:
    """进程内单例 Weaviate v4 客户端。"""
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


def _tenant_kb_filter(tenant_id: UUID, kb_id: UUID | None) -> Filter:
    """构造 tenant_id（及可选 kb_id）过滤条件。"""
    filt = Filter.by_property("tenant_id").equal(str(tenant_id))
    if kb_id:
        filt = filt & Filter.by_property("kb_id").equal(str(kb_id))
    return filt


def _ensure_collection() -> None:
    """创建 DocumentChunk collection（self_provided 向量 + 标量属性）。"""
    client = _client()
    if client.collections.exists(CLASS_NAME):
        return
    client.collections.create(
        name=CLASS_NAME,
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
            ),
        ),
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


class WeaviateVectorStore:
    """Weaviate 向量库实现（VectorStore 协议，含 search_hybrid）。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """保留 host/port 供 health_check 使用。"""
        s = settings or get_settings()
        self._host = s.weaviate_host
        self._port = s.weaviate_port
        self._scheme = s.weaviate_scheme

    @staticmethod
    @lru_cache
    def _store(_dimension: int):
        """按维度缓存 langchain WeaviateVectorStore（维度仅用于 cache key）。"""
        from langchain_weaviate import WeaviateVectorStore as Lc

        return Lc(
            client=_client(),
            index_name=CLASS_NAME,
            text_key=TEXT_KEY,
            embedding=PrecomputedEmbeddings(),
            attributes=list(_LC_ATTRS),
        )

    def ensure_schema(self, dimension: int) -> None:
        """确保 Weaviate collection 存在。"""
        validate_dimension(dimension)
        _ensure_collection()
        self._store(dimension)

    def upsert_chunk(self, record: ChunkVectorRecord) -> str:
        """预计算向量 + add_texts 写入，返回 chunk 主键。"""
        dim = validate_dimension(len(record.vector))
        self.ensure_schema(dim)
        return upsert_add_texts(self._store(dim), record, embedding_attr="_embedding")

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        kb_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """纯向量检索（alpha=1，等价于无 BM25）。"""
        return self.search_hybrid(
            "",
            query_vector=query_vector,
            tenant_id=tenant_id,
            kb_id=kb_id,
            limit=limit,
            alpha=1.0,
        )

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
        """混合检索：alpha=1 偏向量，alpha=0 偏关键词。"""
        dim = validate_dimension(len(query_vector))
        self.ensure_schema(dim)
        store = self._store(dim)
        store._embedding = PrecomputedEmbeddings(query_vector=query_vector)  # noqa: SLF001
        pairs = store.similarity_search_with_score(
            query=query or "",
            k=limit,
            vector=query_vector,
            alpha=max(0.0, min(1.0, alpha)),
            filters=_tenant_kb_filter(tenant_id, kb_id),
        )
        hits = scored_pairs_to_hits(pairs)
        if alpha < 1.0:
            for h in hits:
                h["score_keyword"] = h.get("score")
        return hits

    def delete_by_document(self, document_id: UUID) -> None:
        """按 document_id 属性批量删除。"""
        client = _client()
        if not client.collections.exists(CLASS_NAME):
            return
        client.collections.get(CLASS_NAME).data.delete_many(
            where=Filter.by_property("document_id").equal(str(document_id))
        )

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """按主键删除；LangChain delete 失败时回退 data.delete_by_id。"""
        if not chunk_ids:
            return
        try:
            self._store(get_settings().embedding_vector_dimension).delete(ids=chunk_ids)
        except Exception:
            if not _client().collections.exists(CLASS_NAME):
                return
            col = _client().collections.get(CLASS_NAME)
            for cid in chunk_ids:
                try:
                    col.data.delete_by_id(cid)
                except Exception:
                    pass

    def health_check(self) -> bool:
        """请求 /v1/.well-known/ready 探测服务就绪。"""
        import httpx

        scheme = "https" if self._scheme == "https" else "http"
        url = f"{scheme}://{self._host}:{self._port}/v1/.well-known/ready"
        try:
            with httpx.Client(timeout=3.0) as c:
                return c.get(url).status_code == 200
        except Exception:
            return False
