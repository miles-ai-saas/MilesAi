"""对象存储配置 OBJECT_STORAGE_*。"""

from miles_core.config import Settings


def test_object_storage_env(monkeypatch):
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "s3.example.com")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "my-bucket")

    s = Settings()
    assert s.object_storage_endpoint == "s3.example.com"
    assert s.object_storage_bucket == "my-bucket"
