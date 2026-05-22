"""对象存储抽象（S3 兼容协议）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStorage(Protocol):
    """统一对象存储接口：默认 MinIO，可切换至 OSS / AWS S3 等 S3 兼容端点。"""

    @property
    def default_bucket(self) -> str: ...

    def ensure_bucket(self, bucket: str | None = None) -> None: ...

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str,
        bucket: str | None = None,
    ) -> None: ...

    def download_bytes(self, object_key: str, bucket: str | None = None) -> bytes: ...

    def delete_object(self, object_key: str, bucket: str | None = None) -> None: ...

    def health_check(self) -> bool: ...
