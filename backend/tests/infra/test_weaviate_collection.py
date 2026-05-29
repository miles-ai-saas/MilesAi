"""Weaviate DocumentChunk 集合创建（weaviate-client 4.x 向量距离枚举）。"""

from unittest.mock import MagicMock, patch

from weaviate.classes.config import VectorDistances

from app.infra.vector_store.weaviate import CLASS_NAME, _ensure_collection


def test_ensure_collection_uses_cosine_distance_enum():
    client = MagicMock()
    client.collections.exists.return_value = False

    with patch("app.infra.vector_store.weaviate._client", return_value=client):
        _ensure_collection()

    client.collections.create.assert_called_once()
    kwargs = client.collections.create.call_args.kwargs
    assert kwargs["name"] == CLASS_NAME
    assert "vector_config" in kwargs
    assert kwargs["vector_config"].vectorIndexConfig.distance == VectorDistances.COSINE


def test_ensure_collection_skips_when_exists():
    client = MagicMock()
    client.collections.exists.return_value = True

    with patch("app.infra.vector_store.weaviate._client", return_value=client):
        _ensure_collection()

    client.collections.create.assert_not_called()
