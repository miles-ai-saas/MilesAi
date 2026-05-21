from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.common.exceptions import AppError

settings = get_settings()


@lru_cache
def get_minio() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio | None = None) -> None:
    client = client or get_minio()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def build_object_key(tenant_id: str, kb_id: str, document_id: str, filename: str) -> str:
    return f"{tenant_id}/{kb_id}/{document_id}/{filename}"


def upload_bytes(
    data: bytes,
    object_key: str,
    content_type: str,
    bucket: str | None = None,
) -> None:
    client = get_minio()
    ensure_bucket(client)
    bucket = bucket or settings.minio_bucket
    client.put_object(
        bucket,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_bytes(object_key: str, bucket: str | None = None) -> bytes:
    client = get_minio()
    bucket = bucket or settings.minio_bucket
    try:
        response = client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except S3Error as exc:
        raise AppError(f"MinIO 读取失败: {exc.message}", status_code=500) from exc


def delete_object(object_key: str, bucket: str | None = None) -> None:
    client = get_minio()
    bucket = bucket or settings.minio_bucket
    client.remove_object(bucket, object_key)
