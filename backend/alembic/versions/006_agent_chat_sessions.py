"""智能体对话会话与消息

Revision ID: 006
Revises: 005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agt_chat_sessions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(128), nullable=False, server_default="新对话"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_agt_chat_sessions_tenant_agent_updated",
        "agt_chat_sessions",
        ["tenant_id", "agent_id", "updated_at"],
    )

    op.create_table(
        "agt_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("media", postgresql.JSONB(), nullable=True),
        sa.Column("artifacts", postgresql.JSONB(), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_agt_chat_messages_session_sort",
        "agt_chat_messages",
        ["session_id", "sort_index"],
    )
    op.create_index(
        "idx_agt_chat_messages_tenant_agent",
        "agt_chat_messages",
        ["tenant_id", "agent_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_agt_chat_messages_tenant_agent", table_name="agt_chat_messages")
    op.drop_index("idx_agt_chat_messages_session_sort", table_name="agt_chat_messages")
    op.drop_table("agt_chat_messages")
    op.drop_index("idx_agt_chat_sessions_tenant_agent_updated", table_name="agt_chat_sessions")
    op.drop_table("agt_chat_sessions")
