"""智能体对话会话 ORM（agt_chat_sessions / agt_chat_messages）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class AgentChatSession(Base):
    """对话会话；``id`` 与前端 ``conversation_id`` 一致。"""

    __tablename__ = "agt_chat_sessions"
    __table_args__ = (Index("idx_agt_chat_sessions_tenant_agent_updated", "tenant_id", "agent_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="新对话")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentChatMessage(UUIDPrimaryKeyMixin, Base):
    """会话内单条消息（含 assistant steps）。"""

    __tablename__ = "agt_chat_messages"
    __table_args__ = (
        Index("idx_agt_chat_messages_session_sort", "session_id", "sort_index"),
        Index("idx_agt_chat_messages_tenant_agent", "tenant_id", "agent_id"),
    )

    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    artifacts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
