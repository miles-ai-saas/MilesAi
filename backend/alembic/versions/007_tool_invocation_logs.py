"""tool_invocation_logs 表

Revision ID: 007
Revises: 006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migration_helpers import table_exists

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("tool_invocation_logs"):
        return
    op.create_table(
        "tool_invocation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tool_slug", sa.String(64), nullable=False),
        sa.Column("tool_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("params", JSONB(), nullable=False, server_default="{}"),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("invoke_source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_tool_invocation_logs_tenant_created",
        "tool_invocation_logs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_tool_invocation_logs_tool_slug",
        "tool_invocation_logs",
        ["tenant_id", "tool_slug"],
    )


def downgrade() -> None:
    if not table_exists("tool_invocation_logs"):
        return
    op.drop_index("idx_tool_invocation_logs_tool_slug", table_name="tool_invocation_logs")
    op.drop_index("idx_tool_invocation_logs_tenant_created", table_name="tool_invocation_logs")
    op.drop_table("tool_invocation_logs")
