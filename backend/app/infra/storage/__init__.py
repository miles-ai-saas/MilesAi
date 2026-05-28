"""对象存储层：S3 兼容协议，默认 MinIO，可接 OSS 等。

上传链路：KnowledgeBaseService.upload_document → upload_bytes → ingest 时 download_bytes。
"""

from app.infra.storage.base import ObjectStorage
from app.infra.storage.factory import get_object_storage
from app.infra.storage.resolve import (
    ResolvedObjectStorage,
    resolve_object_storage_async,
    resolve_object_storage_sync,
)
from app.infra.storage.s3 import (
    S3CompatibleObjectStorage,
    build_attachment_object_key,
    build_object_key,
)

__all__ = [
    "ObjectStorage",
    "ResolvedObjectStorage",
    "S3CompatibleObjectStorage",
    "build_attachment_object_key",
    "build_object_key",
    "delete_object",
    "download_bytes",
    "get_object_storage",
    "resolve_object_storage_async",
    "resolve_object_storage_sync",
    "upload_bytes",
]


def upload_bytes(
    data: bytes,
    object_key: str,
    content_type: str,
    bucket: str | None = None,
    *,
    tenant_id=None,
    db=None,
) -> None:
    """上传原始文件到对象存储（同步，API 上传路径）。"""
    resolved = resolve_object_storage_sync(tenant_id, db)
    resolved.storage.upload_bytes(data, object_key, content_type, bucket=bucket)


def download_bytes(
    object_key: str,
    bucket: str | None = None,
    *,
    tenant_id=None,
    db=None,
) -> bytes:
    """Celery ingest 从 OSS 读取文档字节。"""
    resolved = resolve_object_storage_sync(tenant_id, db)
    return resolved.storage.download_bytes(object_key, bucket=bucket)


def delete_object(
    object_key: str,
    bucket: str | None = None,
    *,
    tenant_id=None,
    db=None,
) -> None:
    """删除文档对象（delete_document 时调用，失败可忽略）。"""
    resolved = resolve_object_storage_sync(tenant_id, db)
    resolved.storage.delete_object(object_key, bucket=bucket)
