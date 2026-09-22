"""Milvus 向量存储（Mock MilvusClient）。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_core.infra.vector_store.base import ChunkVectorRecord
from miles_core.infra.vector_store.milvus import (
    MilvusVectorStore,
    _record_to_row,
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


def test_record_to_row_includes_required_metadata():
    record = _sample_record(dim=1024)
    row = _record_to_row(record)
    assert row["tenant_id"] == str(record.tenant_id)
    assert row["kb_id"] == str(record.kb_id)
    assert row["document_id"] == str(record.document_id)
    assert row["chunk_id"] == str(record.chunk_id)
    assert row["vector"] == record.vector


@patch("miles_core.infra.vector_store.milvus._client")
@patch("miles_core.infra.vector_store.milvus._ensure_collection")
def test_upsert_chunk_returns_id(mock_ensure, mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    mock_ensure.return_value = "document_chunk_384"
    client.insert.return_value = {"ids": ["vec-1"]}
    record = _sample_record(external_id="vec-1")

    vid = MilvusVectorStore().upsert_chunk(record)

    assert vid == "vec-1"
    client.insert.assert_called_once()
    call = client.insert.call_args
    assert call.kwargs["collection_name"] == "document_chunk_384"
    assert call.kwargs["data"][0]["vector"] == record.vector


@patch("miles_core.infra.vector_store.milvus._client")
@patch("miles_core.infra.vector_store.milvus._ensure_collection")
def test_search_maps_hits(mock_ensure, mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    mock_ensure.return_value = "document_chunk_384"
    chunk_id = str(uuid4())
    doc_id = str(uuid4())
    client.search.return_value = [
        [
            {
                "distance": 0.2,
                "entity": {
                    "id": "vec-1",
                    "content_preview": "hello",
                    "chunk_id": chunk_id,
                    "document_id": doc_id,
                },
            }
        ]
    ]
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


@patch("miles_core.infra.vector_store.milvus._client")
def test_delete_by_document(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    client.has_collection.return_value = True

    MilvusVectorStore().delete_by_document(uuid4())

    assert client.delete.called


@patch("miles_core.infra.vector_store.milvus._client")
def test_delete_by_chunk_ids(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    client.has_collection.return_value = True

    MilvusVectorStore().delete_by_chunk_ids(["c1"])

    client.delete.assert_called()


@patch("miles_core.infra.vector_store.milvus.MilvusClient")
def test_health_check(mock_client_cls):
    mock_client_cls.return_value.list_collections.return_value = []
    assert MilvusVectorStore().health_check() is True


@patch("miles_core.infra.vector_store.milvus._client")
@patch("miles_core.infra.vector_store.milvus._ensure_collection")
def test_upsert_chunks_batch_insert(mock_ensure, mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    mock_ensure.return_value = "document_chunk_384"
    r1, r2 = _sample_record(external_id="a"), _sample_record(external_id="b")
    client.insert.return_value = {"ids": ["a", "b"]}

    ids = MilvusVectorStore().upsert_chunks([r1, r2])

    assert ids == ["a", "b"]
    client.insert.assert_called_once()
    assert len(client.insert.call_args.kwargs["data"]) == 2


@patch("miles_core.infra.vector_store.milvus._client")
@patch("miles_core.infra.vector_store.milvus._ensure_collection")
def test_upsert_chunks_empty(mock_ensure, mock_client_fn):
    assert MilvusVectorStore().upsert_chunks([]) == []
    mock_client_fn.assert_not_called()


@patch("miles_core.infra.vector_store.milvus._client")
@patch("miles_core.infra.vector_store.milvus._ensure_collection")
def test_upsert_chunk_delegates_to_batch(mock_ensure, mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client
    mock_ensure.return_value = "document_chunk_384"
    client.insert.return_value = {"ids": ["vec-1"]}
    record = _sample_record(external_id="vec-1")
    assert MilvusVectorStore().upsert_chunk(record) == "vec-1"


def test_ensure_collection_skips_second_load(monkeypatch):
    from pymilvus.client.types import LoadState

    from miles_core.infra.vector_store import milvus as m

    m._loaded_collections.clear()
    client = MagicMock()
    client.has_collection.return_value = True
    client.list_indexes.return_value = ["idx"]
    client.get_load_state.return_value = {"state": LoadState.Loaded}
    m._ensure_collection(client, 384)
    m._ensure_collection(client, 384)
    assert client.load_collection.call_count == 1


def test_ensure_collection_reloads_after_unload():
    """进程缓存命中但 Milvus 侧已 unload 时须重新 load。"""
    from pymilvus.client.types import LoadState

    from miles_core.infra.vector_store import milvus as m

    m._loaded_collections.clear()
    client = MagicMock()
    client.has_collection.return_value = True
    client.list_indexes.return_value = ["idx"]
    # 首次：尚未 load → 走 load_collection
    client.get_load_state.return_value = {"state": LoadState.NotLoad}
    m._ensure_collection(client, 768)
    assert client.load_collection.call_count == 1
    assert "document_chunk_768" in m._loaded_collections

    # 模拟外部 unload：缓存仍在，但状态变为 NotLoad
    client.get_load_state.return_value = {"state": LoadState.NotLoad}
    m._ensure_collection(client, 768)
    assert client.load_collection.call_count == 2
