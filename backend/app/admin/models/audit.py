"""运营后台审计日志 ORM（adm_audit_logs）。"""

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """管理员操作审计日志，记录操作者/租户/资源/IP/UA/详情。"""

    __tablename__ = "adm_audit_logs"
    __table_args__ = (
        Index("idx_adm_audit_logs_admin_id", "admin_id"),
        Index("idx_adm_audit_logs_tenant_id", "tenant_id"),
        Index("idx_adm_audit_logs_created_at", "created_at"),
    )

    admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
