"""S3 兼容对象存储实现（MinIO SDK，适用于 MinIO / 阿里云 OSS / AWS S3 等）。

KB 文档路径：{tenant_id}/{kb_id}/{document_id}/{filename}（见 build_object_key）。
"""

from __future__ import annotations

from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.common.exceptions import AppError
from app.core.config import Settings, get_settings


class S3CompatibleObjectStorage:
    """基于 MinIO Python SDK 的 S3 API 客户端。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
        default_bucket: str | None = None,
    ) -> None:
        """从 Settings 或显式参数构造（租户 BYOK 使用显式参数）。"""
        s = settings or get_settings()
        self._endpoint = endpoint if endpoint is not None else s.object_storage_endpoint
        self._access_key = access_key if access_key is not None else s.object_storage_access_key
        self._secret_key = secret_key if secret_key is not None else s.object_storage_secret_key
        self._secure = secure if secure is not None else s.object_storage_secure
        self._region = region if region is not None else s.object_storage_region
        self._default_bucket = (
            default_bucket if default_bucket is not None else s.object_storage_bucket
        )

    @property
    def default_bucket(self) -> str:
        return self._default_bucket

    def _get_client(self) -> Minio:
        """每次调用新建 Minio 客户端（轻量，无长连接池）。"""
        return Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._secure,
            region=self._region,
        )

    def ensure_bucket(self, bucket: str | None = None) -> None:
        """上传前确保 bucket 存在（不存在则创建）。"""
        client = self._get_client()
        name = bucket or self._default_bucket
        if not client.bucket_exists(name):
            client.make_bucket(name)

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str,
        bucket: str | None = None,
    ) -> None:
        """put_object 上传字节流。"""
        client = self._get_client()
        name = bucket or self._default_bucket
        self.ensure_bucket(name)
        client.put_object(
            name,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def download_bytes(self, object_key: str, bucket: str | None = None) -> bytes:
        """get_object 读取全文；S3Error 转为 AppError。"""
        client = self._get_client()
        name = bucket or self._default_bucket
        try:
            response = client.get_object(name, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise AppError(f"对象存储读取失败: {exc.message}", status_code=500) from exc

    def delete_object(self, object_key: str, bucket: str | None = None) -> None:
        """remove_object 删除单个对象。"""
        client = self._get_client()
        name = bucket or self._default_bucket
        client.remove_object(name, object_key)

    def health_check(self) -> bool:
        """探测默认 bucket 是否可访问。"""
        try:
            return self._get_client().bucket_exists(self._default_bucket)
        except Exception:
            return False


def build_object_key(tenant_id: str, kb_id: str, document_id: str, filename: str) -> str:
    """知识库文档对象 key，与向量 metadata object_key 一致便于溯源。"""
    return f"{tenant_id}/{kb_id}/{document_id}/{filename}"


def build_attachment_object_key(tenant_id: str, attachment_id: str, filename: str) -> str:
    """会话附件对象 key（与 KB 文档路径前缀分离）。"""
    return f"{tenant_id}/attachments/{attachment_id}/{filename}"
