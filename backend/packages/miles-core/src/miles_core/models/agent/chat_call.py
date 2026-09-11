"""智能体对话调用记录 ORM（agt_agent_chat_calls）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import UUIDPrimaryKeyMixin


class AgentChatCall(UUIDPrimaryKeyMixin, Base):
    """一轮智能体对话的业务流水（HTTP / WS chat 共用）。"""

    __tablename__ = "agt_agent_chat_calls"
    __table_args__ = (
        Index("idx_agt_agent_chat_calls_tenant_agent_created", "tenant_id", "agent_id", "created_at"),
        Index("idx_agt_agent_chat_calls_tenant_agent_conv", "tenant_id", "agent_id", "conversation_id"),
        Index("idx_agt_agent_chat_calls_tenant_trace", "tenant_id", "trace_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    query_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    steps_summary: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
