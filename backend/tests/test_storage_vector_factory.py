"""对象存储 / 向量存储工厂。"""

import pytest

from app.infra.storage import S3CompatibleObjectStorage, get_object_storage
from app.infra.vector_store import WeaviateVectorStore, get_vector_store
from app.infra.vector_store.pgvector import PgVectorStore


def test_object_storage_default_s3():
    storage = get_object_storage()
    assert isinstance(storage, S3CompatibleObjectStorage)


def test_vector_store_default_weaviate(monkeypatch):
    from app.core.config import Settings
    from app.infra.vector_store import get_vector_store as gvs

    gvs.cache_clear()
    monkeypatch.setattr(
        "app.infra.vector_store.factory.get_settings",
        lambda: Settings(vector_store_backend="weaviate"),
    )
    store = gvs()
    assert isinstance(store, WeaviateVectorStore)
    gvs.cache_clear()


def test_vector_store_pgvector_factory(monkeypatch):
    from app.core.config import Settings
    from app.infra.vector_store import get_vector_store as gvs

    gvs.cache_clear()
    monkeypatch.setattr(
        "app.infra.vector_store.factory.get_settings",
        lambda: Settings(vector_store_backend="pgvector"),
    )
    store = gvs()
    assert isinstance(store, PgVectorStore)
    gvs.cache_clear()


def test_vector_store_milvus_factory(monkeypatch):
    pytest.importorskip("pymilvus")

    from app.core.config import Settings
    from app.infra.vector_store import get_vector_store as gvs
    from app.infra.vector_store.milvus import MilvusVectorStore

    gvs.cache_clear()
    monkeypatch.setattr(
        "app.infra.vector_store.factory.get_settings",
        lambda: Settings(vector_store_backend="milvus"),
    )
    store = gvs()
    assert isinstance(store, MilvusVectorStore)
    gvs.cache_clear()
