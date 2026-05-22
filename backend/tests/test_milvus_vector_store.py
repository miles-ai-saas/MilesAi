"""Milvus 向量存储（Mock MilvusClient，无需真实服务）。"""

import pytest

pytest.importorskip("pymilvus")

from unittest.mock import MagicMock, patch
from uuid import uuid4

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


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_collection_name_by_dimension(mock_client_fn):
    assert collection_name_for_dimension(384) == "document_chunk_384"


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_ensure_schema_creates_collection(mock_client_fn):
    client = MagicMock()
    client.has_collection.return_value = False
    mock_client_fn.return_value = client

    store = MilvusVectorStore()
    store.ensure_schema(384)

    client.create_collection.assert_called_once()
    assert client.create_collection.call_args.kwargs["collection_name"] == "document_chunk_384"
    assert client.create_collection.call_args.kwargs["dimension"] == 384


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_upsert_chunk_returns_id(mock_client_fn):
    client = MagicMock()
    client.has_collection.return_value = True
    mock_client_fn.return_value = client
    record = _sample_record(external_id="vec-1")

    store = MilvusVectorStore()
    vid = store.upsert_chunk(record)

    assert vid == "vec-1"
    client.upsert.assert_called_once()
    row = client.upsert.call_args.kwargs["data"][0]
    assert row["id"] == "vec-1"
    assert row["tenant_id"] == str(record.tenant_id)


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_search_maps_hits(mock_client_fn):
    client = MagicMock()
    client.has_collection.return_value = True
    client.search.return_value = [
        [
            {
                "id": "vec-1",
                "distance": 0.2,
                "entity": {
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "content_preview": "hello",
                },
            }
        ]
    ]
    mock_client_fn.return_value = client
    tenant_id = uuid4()
    kb_id = uuid4()

    store = MilvusVectorStore()
    hits = store.search(
        [0.1] * 384,
        tenant_id=tenant_id,
        kb_id=kb_id,
        limit=5,
    )

    assert len(hits) == 1
    assert hits[0]["vector_id"] == "vec-1"
    assert hits[0]["score"] == 0.8
    assert 'kb_id == "' in client.search.call_args.kwargs["filter"]


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_delete_by_document_scans_collections(mock_client_fn):
    client = MagicMock()
    client.list_collections.return_value = ["document_chunk_384", "other"]
    mock_client_fn.return_value = client
    doc_id = uuid4()

    MilvusVectorStore().delete_by_document(doc_id)

    client.delete.assert_called_once()
    assert client.delete.call_args.kwargs["collection_name"] == "document_chunk_384"


@patch("app.infra.vector_store.milvus._get_milvus_client")
def test_health_check(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    assert MilvusVectorStore().health_check() is True
    client.list_collections.assert_called_once()
