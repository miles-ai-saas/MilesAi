"""对象存储 / 向量存储工厂。"""

import pytest

from app.infra.storage import S3CompatibleObjectStorage, get_object_storage
from app.infra.vector_store import WeaviateVectorStore, get_vector_store
from app.infra.vector_store.pgvector import PgVectorStore


def test_object_storage_default_s3():
    storage = get_object_storage()
    assert isinstance(storage, S3CompatibleObjectStorage)


def test_vector_store_default_weaviate():
    store = get_vector_store()
    assert isinstance(store, WeaviateVectorStore)


def test_vector_store_pgvector_not_implemented(monkeypatch):
    from app.core.config import Settings
    from app.infra.vector_store import factory as vf

    vf.get_vector_store.cache_clear()
    monkeypatch.setattr(
        "app.infra.vector_store.factory.get_settings",
        lambda: Settings(vector_store_backend="pgvector"),
    )
    store = vf.get_vector_store()
    assert isinstance(store, PgVectorStore)
    try:
        store.ensure_schema(384)
    except NotImplementedError as exc:
        assert "pgvector" in str(exc)
    vf.get_vector_store.cache_clear()


def test_vector_store_milvus_factory(monkeypatch):
    pytest.importorskip("pymilvus")

    from app.core.config import Settings
    from app.infra.vector_store import factory as vf
    from app.infra.vector_store.milvus import MilvusVectorStore

    vf.get_vector_store.cache_clear()
    monkeypatch.setattr(
        "app.infra.vector_store.factory.get_settings",
        lambda: Settings(vector_store_backend="milvus"),
    )
    store = vf.get_vector_store()
    assert isinstance(store, MilvusVectorStore)
    vf.get_vector_store.cache_clear()
