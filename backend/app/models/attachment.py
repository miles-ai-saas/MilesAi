import uuid

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Attachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户通用附件：对话、智能体、工作流等上传文件元数据。"""

    __tablename__ = "sys_attachments"
    __table_args__ = (
        Index("idx_sys_attachments_tenant_id", "tenant_id"),
        Index("idx_sys_attachments_resource", "tenant_id", "resource_type", "resource_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    object_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
