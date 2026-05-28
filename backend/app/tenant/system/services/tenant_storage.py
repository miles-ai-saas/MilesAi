"""租户 L2 对象存储 BYOK 配置。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.field_crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.service import BaseService
from app.core.tenant import TenantContext
from app.infra.storage.resolve import resolve_object_storage_async
from app.infra.storage.s3 import S3CompatibleObjectStorage
from app.models.tenant_object_storage import TenantObjectStorageConfig
from app.tenant.audit_log.services.audit_log import write_tenant_audit_log
from app.tenant.system.schemas.tenant_storage import (
    TenantObjectStorageOut,
    TenantObjectStorageTestResult,
    TenantObjectStorageUpsert,
)


class TenantObjectStorageService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_config(self) -> TenantObjectStorageOut:
        row = await self.db.get(TenantObjectStorageConfig, self.ctx.tenant_id)
        if not row:
            return TenantObjectStorageOut(
                tenant_id=self.ctx.tenant_id,
                is_enabled=False,
                source="platform",
            )
        if not row.is_enabled:
            return TenantObjectStorageOut(
                tenant_id=row.tenant_id,
                is_enabled=False,
                endpoint=row.endpoint,
                bucket=row.bucket,
                access_key=row.access_key,
                secret_key_masked=mask_secret(
                    decrypt_secret(row.secret_key_encrypted) if row.secret_key_encrypted else None
                ),
                secure=row.secure,
                region=row.region,
                source="platform",
            )
        secret_plain = (
            decrypt_secret(row.secret_key_encrypted) if row.secret_key_encrypted else ""
        )
        return TenantObjectStorageOut(
            tenant_id=row.tenant_id,
            is_enabled=row.is_enabled,
            endpoint=row.endpoint,
            bucket=row.bucket,
            access_key=row.access_key,
            secret_key_masked=mask_secret(secret_plain),
            secure=row.secure,
            region=row.region,
            source="tenant",
        )

    def _validate_upsert(self, body: TenantObjectStorageUpsert, existing: TenantObjectStorageConfig | None) -> None:
        if not body.is_enabled:
            return
        if not body.endpoint.strip():
            raise BadRequestError("启用租户对象存储时必须填写 endpoint")
        if not body.bucket.strip():
            raise BadRequestError("启用租户对象存储时必须填写 bucket")
        if not body.access_key.strip():
            raise BadRequestError("启用租户对象存储时必须填写 Access Key")
        has_secret = bool(body.secret_key and body.secret_key.strip())
        has_stored = bool(existing and existing.secret_key_encrypted)
        if not has_secret and not has_stored:
            raise BadRequestError("启用租户对象存储时必须填写 Secret Key")

    async def upsert_config(
        self, body: TenantObjectStorageUpsert, *, request=None
    ) -> TenantObjectStorageOut:
        row = await self.db.get(TenantObjectStorageConfig, self.ctx.tenant_id)
        self._validate_upsert(body, row)

        if row is None:
            row = TenantObjectStorageConfig(tenant_id=self.ctx.tenant_id)
            self.db.add(row)

        row.is_enabled = body.is_enabled
        row.endpoint = body.endpoint.strip()
        row.bucket = body.bucket.strip()
        row.access_key = body.access_key.strip()
        row.secure = body.secure
        row.region = body.region.strip() if body.region else None

        if body.secret_key and body.secret_key.strip():
            row.secret_key_encrypted = encrypt_secret(body.secret_key.strip())
        elif body.is_enabled and not row.secret_key_encrypted:
            raise BadRequestError("请填写 Secret Key")

        await self.db.flush()
        await write_tenant_audit_log(
            self.db,
            self.ctx,
            action="config.tenant_object_storage.update",
            resource_type="tenant",
            resource_id=str(self.ctx.tenant_id),
            request=request,
            detail={"is_enabled": body.is_enabled, "bucket": row.bucket},
        )
        return await self.get_config()

    async def test_connection(self, body: TenantObjectStorageUpsert | None = None) -> TenantObjectStorageTestResult:
        """用表单或已保存配置探测 bucket 是否可访问。"""
        if body is not None:
            secret = body.secret_key.strip() if body.secret_key else ""
            if not secret:
                row = await self.db.get(TenantObjectStorageConfig, self.ctx.tenant_id)
                if row and row.secret_key_encrypted:
                    secret = decrypt_secret(row.secret_key_encrypted)
            if not body.endpoint or not body.bucket or not body.access_key or not secret:
                raise BadRequestError("测试连接需填写 endpoint、bucket、access_key 与 secret_key")
            client = S3CompatibleObjectStorage(
                endpoint=body.endpoint.strip(),
                access_key=body.access_key.strip(),
                secret_key=secret,
                secure=body.secure,
                region=body.region,
                default_bucket=body.bucket.strip(),
            )
        else:
            resolved = await resolve_object_storage_async(self.ctx.tenant_id, self.db)
            if resolved.source != "tenant":
                raise BadRequestError("请先启用并保存租户对象存储配置")
            client = resolved.storage

        try:
            ok = client.health_check()
        except Exception as exc:
            return TenantObjectStorageTestResult(ok=False, message=str(exc)[:500])
        if ok:
            return TenantObjectStorageTestResult(ok=True, message="连接成功，存储桶可访问")
        return TenantObjectStorageTestResult(ok=False, message="无法访问存储桶，请检查 endpoint 与凭证")
