"""L1/L2 对象存储解析：租户 BYOK 覆盖部署级默认配置。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.field_crypto import decrypt_secret
from app.infra.storage.s3 import S3CompatibleObjectStorage
from app.models.storage.tenant_object_storage import TenantObjectStorageConfig


@dataclass(frozen=True)
class ResolvedObjectStorage:
    """解析后的存储客户端与默认桶。"""

    storage: S3CompatibleObjectStorage
    default_bucket: str
    source: str  # "platform" | "tenant"


def _storage_from_tenant_row(row: TenantObjectStorageConfig) -> S3CompatibleObjectStorage:
    secret = decrypt_secret(row.secret_key_encrypted) if row.secret_key_encrypted else ""
    return S3CompatibleObjectStorage(
        endpoint=row.endpoint,
        access_key=row.access_key,
        secret_key=secret,
        secure=row.secure,
        region=row.region,
        default_bucket=row.bucket,
    )


def _storage_from_settings(settings: Settings | None = None) -> S3CompatibleObjectStorage:
    return S3CompatibleObjectStorage(settings=settings)


def resolve_object_storage_sync(
    tenant_id: UUID | None,
    db: Session | None,
) -> ResolvedObjectStorage:
    """同步解析（Celery / ingest Worker）。"""
    settings = get_settings()
    if tenant_id is not None and db is not None:
        row = db.get(TenantObjectStorageConfig, tenant_id)
        if row and row.is_enabled and row.endpoint and row.bucket and row.access_key:
            client = _storage_from_tenant_row(row)
            return ResolvedObjectStorage(
                storage=client,
                default_bucket=row.bucket,
                source="tenant",
            )
    client = _storage_from_settings(settings)
    return ResolvedObjectStorage(
        storage=client,
        default_bucket=settings.object_storage_bucket,
        source="platform",
    )


async def resolve_object_storage_async(
    tenant_id: UUID | None,
    db: AsyncSession | None,
) -> ResolvedObjectStorage:
    """异步解析（FastAPI 请求路径）。"""
    settings = get_settings()
    if tenant_id is not None and db is not None:
        row = await db.get(TenantObjectStorageConfig, tenant_id)
        if row and row.is_enabled and row.endpoint and row.bucket and row.access_key:
            client = _storage_from_tenant_row(row)
            return ResolvedObjectStorage(
                storage=client,
                default_bucket=row.bucket,
                source="tenant",
            )
    client = _storage_from_settings(settings)
    return ResolvedObjectStorage(
        storage=client,
        default_bucket=settings.object_storage_bucket,
        source="platform",
    )


async def resolve_default_bucket_async(tenant_id: UUID, db: AsyncSession) -> str:
    """仅取租户解析后的默认桶名（供上传路径拼接）。"""
    return (await resolve_object_storage_async(tenant_id, db)).default_bucket
