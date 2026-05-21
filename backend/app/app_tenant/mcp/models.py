import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class McpStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class McpService(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_mcp_services"
    __table_args__ = (
        Index("idx_tool_mcp_services_tenant_id", "tenant_id"),
        Index("un_tool_mcp_services_tenant_id_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(512), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), default="sse", nullable=False)
    tools_cache: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[McpStatus] = mapped_column(
        SAEnum(McpStatus, name="mcp_status", values_callable=lambda x: [e.value for e in x]),
        default=McpStatus.INACTIVE,
        nullable=False,
    )
