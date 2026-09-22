from unittest.mock import MagicMock, patch
from uuid import uuid4

from miles_ai.rag.index.gateway import ChunkVectorWrite, upsert_chunk_vectors


@patch("miles_ai.rag.index.gateway.get_vector_store")
def test_upsert_chunk_vectors_maps_records(mock_get):
    store = MagicMock()
    mock_get.return_value = store
    store.upsert_chunks.return_value = ["v1", "v2"]
    items = [
        ChunkVectorWrite(
            vector=[0.1, 0.2],
            tenant_id=uuid4(),
            kb_id=uuid4(),
            document_id=uuid4(),
            chunk_id=uuid4(),
            content_preview="a",
            object_key="k",
        ),
        ChunkVectorWrite(
            vector=[0.3, 0.4],
            tenant_id=uuid4(),
            kb_id=uuid4(),
            document_id=uuid4(),
            chunk_id=uuid4(),
            content_preview="b",
            object_key="k",
        ),
    ]
    assert upsert_chunk_vectors(items) == ["v1", "v2"]
    store.upsert_chunks.assert_called_once()
    assert len(store.upsert_chunks.call_args.args[0]) == 2
