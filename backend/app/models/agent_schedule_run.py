"""智能体定时任务执行历史（agt_schedule_runs）。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AgentScheduleRunStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class AgentScheduleRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agt_schedule_runs"
    __table_args__ = (
        Index("idx_agt_schedule_runs_schedule_id", "schedule_id"),
        Index("idx_agt_schedule_runs_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
