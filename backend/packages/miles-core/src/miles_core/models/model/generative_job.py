"""异步生成任务（生视频等）。"""

import enum
import uuid

from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 异步生成任务状态。
class GenerativeJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerativeJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """异步生成任务（生图/生视频）记录与进度。"""

    __tablename__ = "generative_jobs"
    __table_args__ = (
        Index("idx_generative_jobs_tenant_id", "tenant_id"),
        Index("idx_generative_jobs_status", "status"),
        Index("idx_generative_jobs_trace_id", "trace_id"),
    )

    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[GenerativeJobStatus] = mapped_column(
        Enum(
            GenerativeJobStatus,
            name="generative_job_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=GenerativeJobStatus.PENDING,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(256), nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
