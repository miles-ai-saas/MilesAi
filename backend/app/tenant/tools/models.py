"""工具注册表 ORM：租户自定义工具与调用审计。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 工具类型：HTTP 出站调用或 Runner 沙箱脚本。
class ToolType(str, enum.Enum):
    HTTP = "http"
    SCRIPT = "script"  # v2：MCP Runner 沙箱执行


class Tool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户自定义工具定义；HTTP/脚本周配置存于 ``config``。"""

    __tablename__ = "tool_tools"
    __table_args__ = (
        Index("idx_tool_tools_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "slug", name="un_tool_tools_tenant_id_slug"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_type: Mapped[ToolType] = mapped_column(
        SAEnum(ToolType, name="tool_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    require_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ToolInvocationLog(UUIDPrimaryKeyMixin, Base):
    """工具调用审计（试调用 / Agent / 流程）。"""

    __tablename__ = "tool_invocation_logs"
    __table_args__ = (
        Index("idx_tool_invocation_logs_tenant_created", "tenant_id", "created_at"),
        Index("idx_tool_invocation_logs_tool_slug", "tenant_id", "tool_slug"),
        Index("idx_tool_invocation_logs_trace_id", "trace_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tool_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    invoke_source: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
