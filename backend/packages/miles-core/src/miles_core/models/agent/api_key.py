"""智能体 API Key ORM（agt_agent_api_keys）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import AuditTimestampMixin, UUIDPrimaryKeyMixin


class AgentApiKey(UUIDPrimaryKeyMixin, AuditTimestampMixin, Base):
    """按智能体绑定的正式 API Key；吊销用 revoked_at，明文不落库。"""

    __tablename__ = "agt_agent_api_keys"
    __table_args__ = (
        Index("idx_agt_agent_api_keys_tenant_agent", "tenant_id", "agent_id"),
        UniqueConstraint("key_hash", name="uq_agt_agent_api_keys_key_hash"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
