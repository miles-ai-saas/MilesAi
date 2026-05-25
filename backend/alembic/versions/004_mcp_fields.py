"""MCP 服务描述、连接配置与同步错误

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from migration_helpers import add_column_if_missing, drop_column_if_exists

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    add_column_if_missing(
        "tool_mcp_services",
        sa.Column("description", sa.String(512), nullable=True),
    )
    add_column_if_missing(
        "tool_mcp_services",
        sa.Column("connection_config", JSONB, nullable=False, server_default="{}"),
    )
    add_column_if_missing(
        "tool_mcp_services",
        sa.Column("sync_error", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("tool_mcp_services", "sync_error")
    drop_column_if_exists("tool_mcp_services", "connection_config")
    drop_column_if_exists("tool_mcp_services", "description")
