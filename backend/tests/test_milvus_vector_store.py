"""Milvus 向量存储（Mock langchain_milvus.Milvus）。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.infra.vector_store.base import ChunkVectorRecord
from app.infra.vector_store.milvus import (
    MilvusVectorStore,
    collection_name_for_dimension,
)


def _sample_record(*, dim: int = 384, external_id: str | None = None) -> ChunkVectorRecord:
    return ChunkVectorRecord(
        vector=[0.1] * dim,
        tenant_id=uuid4(),
        kb_id=uuid4(),
        document_id=uuid4(),
        chunk_id=uuid4(),
        content_preview="preview",
        object_key="tenant/kb/doc.txt",
        page_no=1,
        external_id=external_id,
    )


def test_collection_name_by_dimension():
    assert collection_name_for_dimension(384) == "document_chunk_384"


@patch("app.infra.vector_store.milvus.MilvusVectorStore._store")
def test_upsert_chunk_returns_id(mock_lc_store):
    store = MagicMock()
    store.add_texts.return_value = ["vec-1"]
    mock_lc_store.return_value = store
    record = _sample_record(external_id="vec-1")

    vid = MilvusVectorStore().upsert_chunk(record)

    assert vid == "vec-1"
    store.add_texts.assert_called_once()


@patch("app.infra.vector_store.milvus.MilvusVectorStore._store")
def test_search_maps_hits(mock_lc_store):
    from langchain_core.documents import Document

    doc = Document(
        page_content="hello",
        metadata={"chunk_id": "c1", "document_id": "d1"},
        id="vec-1",
    )
    store = MagicMock()
    store.col = MagicMock()
    store.similarity_search_with_score_by_vector.return_value = [(doc, 0.2)]
    mock_lc_store.return_value = store
    tenant_id = uuid4()
    kb_id = uuid4()

    hits = MilvusVectorStore().search(
        [0.1] * 384,
        tenant_id=tenant_id,
        kb_id=kb_id,
        limit=5,
    )

    assert len(hits) == 1
    assert hits[0]["vector_id"] == "vec-1"
    assert hits[0]["score"] == pytest.approx(0.8, rel=1e-3)


@patch("app.infra.vector_store.milvus.MilvusVectorStore._store")
def test_delete_by_document(mock_lc_store):
    store = MagicMock()
    store.client.has_collection.return_value = True
    mock_lc_store.return_value = store

    MilvusVectorStore().delete_by_document(uuid4())

    store.delete.assert_called()


@patch("app.infra.vector_store.milvus.MilvusVectorStore._store")
def test_health_check(mock_lc_store):
    with patch("pymilvus.MilvusClient") as mock_client_cls:
        mock_client_cls.return_value.list_collections.return_value = []
        assert MilvusVectorStore().health_check() is True
