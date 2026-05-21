import enum
import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ToolType(str, enum.Enum):
    BUILTIN = "builtin"
    HTTP = "http"


class Tool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_tools"
    __table_args__ = (
        Index("idx_tool_tools_tenant_id", "tenant_id"),
        Index("un_tool_tools_tenant_id_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_type: Mapped[ToolType] = mapped_column(
        SAEnum(ToolType, name="tool_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
