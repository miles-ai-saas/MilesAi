"""Weaviate / pgvector 批量 upsert_chunks。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_core.infra.vector_store.base import ChunkVectorRecord
from miles_core.infra.vector_store.pgvector import PgVectorStore
from miles_core.infra.vector_store.weaviate import WeaviateVectorStore


def _rec(dim: int = 384) -> ChunkVectorRecord:
    return ChunkVectorRecord(
        vector=[0.1] * dim,
        tenant_id=uuid4(),
        kb_id=uuid4(),
        document_id=uuid4(),
        chunk_id=uuid4(),
        content_preview="p",
        object_key="k",
    )


@patch.object(PgVectorStore, "_store")
def test_pg_upsert_chunks_calls_add_embeddings_once(mock_store_fn):
    store = MagicMock()
    mock_store_fn.return_value = store
    store.add_embeddings.return_value = ["id1", "id2"]
    r1, r2 = _rec(), _rec()
    ids = PgVectorStore().upsert_chunks([r1, r2])
    assert ids == ["id1", "id2"]
    assert store.add_embeddings.call_count == 1
    call_kwargs = store.add_embeddings.call_args.kwargs
    assert len(call_kwargs["texts"]) == 2
    assert len(call_kwargs["embeddings"]) == 2
    assert len(call_kwargs["metadatas"]) == 2
    assert len(call_kwargs["ids"]) == 2


@patch.object(PgVectorStore, "_store")
def test_pg_upsert_chunks_empty(mock_store_fn):
    assert PgVectorStore().upsert_chunks([]) == []
    mock_store_fn.assert_not_called()


@patch.object(PgVectorStore, "_store")
def test_pg_upsert_chunks_rejects_mixed_dims(mock_store_fn):
    with pytest.raises(ValueError, match="同一批次向量维度必须一致"):
        PgVectorStore().upsert_chunks([_rec(384), _rec(768)])
    mock_store_fn.assert_not_called()


@patch.object(PgVectorStore, "_store")
def test_pg_upsert_chunk_delegates_to_batch(mock_store_fn):
    store = MagicMock()
    mock_store_fn.return_value = store
    store.add_embeddings.return_value = ["solo"]
    assert PgVectorStore().upsert_chunk(_rec()) == "solo"
    assert store.add_embeddings.call_count == 1


@patch("miles_core.infra.vector_store.weaviate._ensure_collection")
@patch.object(WeaviateVectorStore, "_store")
def test_weaviate_upsert_chunks_calls_add_texts_once(mock_store_fn, _mock_ensure):
    store = MagicMock()
    mock_store_fn.return_value = store
    store.add_texts.return_value = ["id1", "id2"]
    r1, r2 = _rec(), _rec()
    ids = WeaviateVectorStore().upsert_chunks([r1, r2])
    assert ids == ["id1", "id2"]
    assert store.add_texts.call_count == 1
    call_kwargs = store.add_texts.call_args.kwargs
    assert len(call_kwargs["texts"]) == 2
    assert len(call_kwargs["metadatas"]) == 2
    assert len(call_kwargs["ids"]) == 2


@patch("miles_core.infra.vector_store.weaviate._ensure_collection")
@patch.object(WeaviateVectorStore, "_store")
def test_weaviate_upsert_chunks_empty(mock_store_fn, mock_ensure):
    assert WeaviateVectorStore().upsert_chunks([]) == []
    mock_store_fn.assert_not_called()
    mock_ensure.assert_not_called()


@patch("miles_core.infra.vector_store.weaviate._ensure_collection")
@patch.object(WeaviateVectorStore, "_store")
def test_weaviate_upsert_chunks_rejects_mixed_dims(mock_store_fn, mock_ensure):
    with pytest.raises(ValueError, match="同一批次向量维度必须一致"):
        WeaviateVectorStore().upsert_chunks([_rec(384), _rec(768)])
    mock_store_fn.assert_not_called()
    mock_ensure.assert_not_called()


@patch("miles_core.infra.vector_store.weaviate._ensure_collection")
@patch.object(WeaviateVectorStore, "_store")
def test_weaviate_upsert_chunk_delegates_to_batch(mock_store_fn, _mock_ensure):
    store = MagicMock()
    mock_store_fn.return_value = store
    store.add_texts.return_value = ["solo"]
    assert WeaviateVectorStore().upsert_chunk(_rec()) == "solo"
    assert store.add_texts.call_count == 1
