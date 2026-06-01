"""交付域 · 工作包里程碑 ORM。"""

import uuid

from sqlalchemy import Date, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizMilestone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """工作包里程碑——关键节点与到期跟踪。"""

    __tablename__ = "biz_milestones"
    __table_args__ = (
        Index("idx_biz_ms_tenant", "tenant_id"),
        Index("idx_biz_ms_wp", "tenant_id", "work_package_id"),
        Index("idx_biz_ms_project", "tenant_id", "project_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    work_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    due_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_reminder_sent_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
