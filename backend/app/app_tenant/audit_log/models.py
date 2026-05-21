import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TenantAuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户内操作审计（与运营 adm_audit_logs 分离）。"""

    __tablename__ = "aud_logs"
    __table_args__ = (
        Index("idx_aud_logs_tenant_id", "tenant_id"),
        Index("idx_aud_logs_user_id", "user_id"),
        Index("idx_aud_logs_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
