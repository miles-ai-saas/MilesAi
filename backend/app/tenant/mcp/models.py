"""MCP 服务注册表 ORM（表 tool_mcp_services）。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class McpStatus(str, enum.Enum):
    """同步与可用性状态，供工作台卡片展示。"""

    ACTIVE = "active"  # 最近一次 sync 成功且有工具列表
    INACTIVE = "inactive"  # 新建或未成功同步
    ERROR = "error"  # sync 失败或 STDIO 暂不支持


class McpService(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    租户级 MCP 端点配置。

    transport 决定 client 走 Legacy SSE / Streamable HTTP /（规划）STDIO Runner。
    tools_cache 为最近一次 tools/list 快照，供智能体提示与工具目录聚合。
    """

    __tablename__ = "tool_mcp_services"
    __table_args__ = (
        Index("idx_tool_mcp_services_tenant_id", "tenant_id"),
        Index("un_tool_mcp_services_tenant_id_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # HTTP(S) 完整 URL，或 STDIO 占位 stdio://{name}
    endpoint_url: Mapped[str] = mapped_column(String(512), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), default="sse", nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # headers、timeout_sec、mcp_initialize、session_id 等，见 docs/guides/mcp.md
    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    sync_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tools_cache: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[McpStatus] = mapped_column(
        SAEnum(McpStatus, name="mcp_status", values_callable=lambda x: [e.value for e in x]),
        default=McpStatus.INACTIVE,
        nullable=False,
    )
