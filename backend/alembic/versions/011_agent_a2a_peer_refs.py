"""自定义智能体引用外部 A2A Peer

Revision ID: 011
Revises: 010
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if inspect(op.get_bind()).has_table("agt_agent_a2a_peer_refs"):
        return
    op.create_table(
        "agt_agent_a2a_peer_refs",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("peer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_hint", sa.String(64), nullable=True),
        sa.Column("trigger_keywords", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agt_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["peer_id"], ["agt_a2a_peers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "peer_id"),
    )
    op.create_index(
        "idx_agt_agent_a2a_peer_refs_agent",
        "agt_agent_a2a_peer_refs",
        ["agent_id"],
    )
    op.create_index(
        "idx_agt_agent_a2a_peer_refs_peer",
        "agt_agent_a2a_peer_refs",
        ["peer_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_agt_agent_a2a_peer_refs_peer", table_name="agt_agent_a2a_peer_refs")
    op.drop_index("idx_agt_agent_a2a_peer_refs_agent", table_name="agt_agent_a2a_peer_refs")
    op.drop_table("agt_agent_a2a_peer_refs")
