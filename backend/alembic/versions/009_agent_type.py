"""agt_agents 增加 agent_type（custom | a2a）

Revision ID: 009
Revises: 008
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

agent_type_enum = sa.Enum("custom", "a2a", name="agent_type", create_type=True)


def upgrade() -> None:
    agent_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "agt_agents",
        sa.Column(
            "agent_type",
            agent_type_enum,
            server_default="custom",
            nullable=False,
        ),
    )
    op.create_index("idx_agt_agents_tenant_type", "agt_agents", ["tenant_id", "agent_type"])


def downgrade() -> None:
    op.drop_index("idx_agt_agents_tenant_type", table_name="agt_agents")
    op.drop_column("agt_agents", "agent_type")
    agent_type_enum.drop(op.get_bind(), checkfirst=True)
