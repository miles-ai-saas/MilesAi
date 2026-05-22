import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class KbSearchLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "kb_search_logs"
    __table_args__ = (
        Index("idx_kb_search_logs_tenant_created", "tenant_id", "created_at"),
        Index("idx_kb_search_logs_kb_created", "kb_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kb_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(32), default="vector", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
