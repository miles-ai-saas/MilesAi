"""Celery 任务镜像表（与 Worker sync_task_by_celery_id 同步）。"""

import enum
import uuid

from sqlalchemy import Enum, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 任务状态，与 Celery 任务状态映射。
class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CeleryTaskRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """resource_type=document 时 resource_id 指向 kb_documents.id。"""

    __tablename__ = "task_records"
    __table_args__ = (
        Index("idx_task_records_tenant_id", "tenant_id"),
        UniqueConstraint("celery_task_id", name="uk_task_records_celery_task_id"),
        Index("idx_task_records_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    celery_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=lambda x: [e.value for e in x]),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
