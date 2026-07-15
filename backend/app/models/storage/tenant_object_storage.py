"""租户 L2 对象存储 BYOK 配置（S3 兼容 API）。"""

import uuid

from sqlalchemy import Boolean, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import AuditTimestampMixin


class TenantObjectStorageConfig(AuditTimestampMixin, Base):
    """每租户可选独立对象存储桶与凭证；未启用时走 L1 部署级 MinIO/OSS。"""

    __tablename__ = "sys_tenant_object_storage"
    __table_args__ = (Index("idx_sys_tenant_object_storage_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    bucket: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    access_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    secret_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    secure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
