"""智能体对话调用记录表

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agt_agent_chat_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.String(128), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("route", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("query_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("steps_summary", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_agt_agent_chat_calls_tenant_agent_created",
        "agt_agent_chat_calls",
        ["tenant_id", "agent_id", "created_at"],
    )
    op.create_index(
        "idx_agt_agent_chat_calls_tenant_agent_conv",
        "agt_agent_chat_calls",
        ["tenant_id", "agent_id", "conversation_id"],
    )
    op.create_index(
        "idx_agt_agent_chat_calls_tenant_trace",
        "agt_agent_chat_calls",
        ["tenant_id", "trace_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_agt_agent_chat_calls_tenant_trace", table_name="agt_agent_chat_calls")
    op.drop_index("idx_agt_agent_chat_calls_tenant_agent_conv", table_name="agt_agent_chat_calls")
    op.drop_index("idx_agt_agent_chat_calls_tenant_agent_created", table_name="agt_agent_chat_calls")
    op.drop_table("agt_agent_chat_calls")
