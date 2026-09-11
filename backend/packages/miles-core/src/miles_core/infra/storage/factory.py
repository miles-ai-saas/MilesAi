"""对象存储工厂（L4）。

部署级 OBJECT_STORAGE_BACKEND；租户级独立 bucket 为二期规划。
"""

from __future__ import annotations

from functools import lru_cache

from miles_core.config import get_settings
from miles_core.infra.storage.base import ObjectStorage
from miles_core.infra.storage.s3 import S3CompatibleObjectStorage

_SUPPORTED = frozenset({"s3"})


@lru_cache
def get_object_storage() -> ObjectStorage:
    """按 OBJECT_STORAGE_BACKEND 返回单例（当前仅 s3 兼容实现）。"""
    backend = get_settings().object_storage_backend.strip().lower()
    if backend not in _SUPPORTED:
        raise ValueError(f"不支持的 OBJECT_STORAGE_BACKEND={backend!r}，当前实现: {', '.join(sorted(_SUPPORTED))}（均为 S3 兼容 API）")
    return S3CompatibleObjectStorage()
