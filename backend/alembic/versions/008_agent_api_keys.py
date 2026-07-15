"""agent api keys + chat call source

Revision ID: 008
Revises: 007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agt_agent_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_agt_agent_api_keys_tenant_agent", "agt_agent_api_keys", ["tenant_id", "agent_id"])
    op.create_index("uq_agt_agent_api_keys_key_hash", "agt_agent_api_keys", ["key_hash"], unique=True)
    op.add_column("agt_agent_chat_calls", sa.Column("source", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("agt_agent_chat_calls", "source")
    op.drop_index("uq_agt_agent_api_keys_key_hash", table_name="agt_agent_api_keys")
    op.drop_index("idx_agt_agent_api_keys_tenant_agent", table_name="agt_agent_api_keys")
    op.drop_table("agt_agent_api_keys")
