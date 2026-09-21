"""向量库：Document 映射与工厂。"""

from uuid import uuid4

from miles_core.infra.vector_store import get_vector_store
from miles_core.infra.vector_store.base import ChunkVectorRecord
from miles_core.infra.vector_store.documents import (
    METADATA_CHUNK_ID,
    METADATA_KB_ID,
    METADATA_TENANT_ID,
    chunk_record_to_document,
    document_to_chunk_record,
    documents_to_hits,
    hit_to_document,
)
from miles_core.infra.vector_store.precomputed import PrecomputedEmbeddings


def test_chunk_record_document_roundtrip_metadata():
    tenant_id = uuid4()
    kb_id = uuid4()
    doc_id = uuid4()
    chunk_id = uuid4()
    record = ChunkVectorRecord(
        vector=[0.1, 0.2],
        tenant_id=tenant_id,
        kb_id=kb_id,
        document_id=doc_id,
        chunk_id=chunk_id,
        content_preview="hello world",
        object_key="t/k/d/f.txt",
        page_no=1,
        external_id=str(chunk_id),
    )
    doc = chunk_record_to_document(record)
    assert doc.page_content == "hello world"
    assert doc.metadata[METADATA_TENANT_ID] == str(tenant_id)
    assert doc.metadata[METADATA_KB_ID] == str(kb_id)
    assert doc.metadata[METADATA_CHUNK_ID] == str(chunk_id)

    back = document_to_chunk_record(
        doc,
        vector=record.vector,
        tenant_id=tenant_id,
        kb_id=kb_id,
        document_id=doc_id,
    )
    assert back.chunk_id == chunk_id


def test_hit_document_roundtrip():
    hit = {
        "vector_id": "v1",
        "chunk_id": "c1",
        "document_id": "d1",
        "content_preview": "snippet",
        "score": 0.88,
    }
    hits = documents_to_hits([hit_to_document(hit)])
    assert hits[0]["chunk_id"] == "c1"
    assert hits[0]["score"] == 0.88


def test_precomputed_embeddings_batch():
    emb = PrecomputedEmbeddings([[1.0, 2.0], [3.0, 4.0]])
    assert emb.embed_documents(["a", "b"]) == [[1.0, 2.0], [3.0, 4.0]]


def _clear_factory_cache(monkeypatch, backend: str):
    from miles_core.config import get_settings

    monkeypatch.setenv("VECTOR_STORE_BACKEND", backend)
    from miles_core.infra.vector_store import get_vector_store as gvs

    get_settings.cache_clear()
    gvs.cache_clear()


def test_factory_weaviate(monkeypatch):
    _clear_factory_cache(monkeypatch, "weaviate")
    from miles_core.infra.vector_store.weaviate import WeaviateVectorStore

    assert isinstance(get_vector_store(), WeaviateVectorStore)


def test_factory_milvus(monkeypatch):
    _clear_factory_cache(monkeypatch, "milvus")
    from miles_core.infra.vector_store.milvus import MilvusVectorStore

    assert isinstance(get_vector_store(), MilvusVectorStore)


def test_factory_pgvector(monkeypatch):
    _clear_factory_cache(monkeypatch, "pgvector")
    from miles_core.infra.vector_store.pgvector import PgVectorStore

    assert isinstance(get_vector_store(), PgVectorStore)
