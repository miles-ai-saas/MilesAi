"""A2A 外部 Agent 登记与宿主绑定表

Revision ID: 010
Revises: 009
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False：避免 create_table 再次 CREATE TYPE（枚举由 _ensure_enum 单独创建）
a2a_peer_status = postgresql.ENUM(
    "pending",
    "active",
    "error",
    "inactive",
    name="a2a_peer_status",
    create_type=False,
)


def _ensure_a2a_peer_status_enum() -> None:
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE a2a_peer_status AS ENUM (
                    'pending', 'active', 'error', 'inactive'
                );
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    _ensure_a2a_peer_status_enum()

    if not insp.has_table("agt_a2a_peers"):
        op.create_table(
            "agt_a2a_peers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("base_url", sa.String(512), nullable=True),
            sa.Column("agent_card_url", sa.String(1024), nullable=False),
            sa.Column("agent_card_json", postgresql.JSONB(), server_default="{}", nullable=False),
            sa.Column("auth_config", postgresql.JSONB(), server_default="{}", nullable=False),
            sa.Column("card_display_name", sa.String(256), nullable=True),
            sa.Column("status", a2a_peer_status, server_default="pending", nullable=False),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
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
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("idx_agt_a2a_peers_tenant_id", "agt_a2a_peers", ["tenant_id"])
        op.create_index(
            "un_agt_a2a_peers_tenant_name",
            "agt_a2a_peers",
            ["tenant_id", "name"],
            unique=True,
        )

    if not insp.has_table("agt_a2a_peer_bindings"):
        op.create_table(
            "agt_a2a_peer_bindings",
            sa.Column("parent_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("peer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_hint", sa.String(64), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
            sa.ForeignKeyConstraint(["parent_agent_id"], ["agt_agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["peer_id"], ["agt_a2a_peers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("parent_agent_id", "peer_id"),
        )
        op.create_index(
            "idx_agt_a2a_peer_bindings_parent",
            "agt_a2a_peer_bindings",
            ["parent_agent_id"],
        )
        op.create_index(
            "idx_agt_a2a_peer_bindings_peer",
            "agt_a2a_peer_bindings",
            ["peer_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if insp.has_table("agt_a2a_peer_bindings"):
        op.drop_index("idx_agt_a2a_peer_bindings_peer", table_name="agt_a2a_peer_bindings")
        op.drop_index("idx_agt_a2a_peer_bindings_parent", table_name="agt_a2a_peer_bindings")
        op.drop_table("agt_a2a_peer_bindings")

    if insp.has_table("agt_a2a_peers"):
        op.drop_index("un_agt_a2a_peers_tenant_name", table_name="agt_a2a_peers")
        op.drop_index("idx_agt_a2a_peers_tenant_id", table_name="agt_a2a_peers")
        op.drop_table("agt_a2a_peers")

    op.execute(sa.text("DROP TYPE IF EXISTS a2a_peer_status"))
