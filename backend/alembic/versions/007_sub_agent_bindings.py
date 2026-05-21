"""主智能体绑定子智能体

Revision ID: 007
Revises: 006
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agt_sub_agent_bindings",
        sa.Column("parent_agent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("child_agent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_hint", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "idx_agt_sub_agent_bindings_parent",
        "agt_sub_agent_bindings",
        ["parent_agent_id"],
    )
    op.create_index(
        "idx_agt_sub_agent_bindings_child",
        "agt_sub_agent_bindings",
        ["child_agent_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_agt_sub_agent_bindings_child", table_name="agt_sub_agent_bindings")
    op.drop_index("idx_agt_sub_agent_bindings_parent", table_name="agt_sub_agent_bindings")
    op.drop_table("agt_sub_agent_bindings")
