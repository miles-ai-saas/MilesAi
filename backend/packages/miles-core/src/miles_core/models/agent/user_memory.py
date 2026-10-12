"""跨会话用户记忆 ORM（agt_user_agent_memories）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import UUIDPrimaryKeyMixin


class AgentUserMemory(UUIDPrimaryKeyMixin, Base):
    """按 (租户, 用户, 智能体, kind) 唯一的长期记忆条目。"""

    __tablename__ = "agt_user_agent_memories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "agent_id",
            "kind",
            name="uk_agt_user_agent_memories_tenant_user_agent_kind",
        ),
        Index("idx_agt_user_agent_memories_tenant_user_agent", "tenant_id", "user_id", "agent_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 内容向量（float 数组）；用于 ``recall_mode=relevant`` 相关性排序
    content_embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
