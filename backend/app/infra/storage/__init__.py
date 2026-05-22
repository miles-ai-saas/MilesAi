"""对象存储层：S3 兼容协议，默认 MinIO，可接 OSS 等。"""

from app.infra.storage.base import ObjectStorage
from app.infra.storage.factory import get_object_storage
from app.infra.storage.s3 import (
    S3CompatibleObjectStorage,
    build_attachment_object_key,
    build_object_key,
)

__all__ = [
    "ObjectStorage",
    "S3CompatibleObjectStorage",
    "build_attachment_object_key",
    "build_object_key",
    "delete_object",
    "download_bytes",
    "get_object_storage",
    "upload_bytes",
]


def upload_bytes(
    data: bytes,
    object_key: str,
    content_type: str,
    bucket: str | None = None,
) -> None:
    get_object_storage().upload_bytes(data, object_key, content_type, bucket=bucket)


def download_bytes(object_key: str, bucket: str | None = None) -> bytes:
    return get_object_storage().download_bytes(object_key, bucket=bucket)


def delete_object(object_key: str, bucket: str | None = None) -> None:
    get_object_storage().delete_object(object_key, bucket=bucket)
