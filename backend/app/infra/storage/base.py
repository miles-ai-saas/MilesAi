"""对象存储抽象（S3 兼容协议）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStorage(Protocol):
    """统一对象存储接口：默认 MinIO，可切换至 OSS / AWS S3 等 S3 兼容端点。"""

    @property
    def default_bucket(self) -> str:
        """默认桶名。"""
        ...

    def ensure_bucket(self, bucket: str | None = None) -> None:
        """确保目标桶存在（不存在则创建）。"""
        ...

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str,
        bucket: str | None = None,
    ) -> None:
        """上传字节流到指定 object key；``bucket`` 缺省用默认桶。"""
        ...

    def download_bytes(self, object_key: str, bucket: str | None = None) -> bytes:
        """按 object key 读取完整字节内容。"""
        ...

    def delete_object(self, object_key: str, bucket: str | None = None) -> None:
        """删除单个对象。"""
        ...

    def health_check(self) -> bool:
        """探测对象存储后端连通性。"""
        ...
