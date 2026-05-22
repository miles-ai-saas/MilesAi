"""A2A 宿主绑定表增加 trigger_keywords

Revision ID: 012
Revises: 011
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("agt_a2a_peer_bindings")}
    if "trigger_keywords" in cols:
        return
    op.add_column(
        "agt_a2a_peer_bindings",
        sa.Column(
            "trigger_keywords",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agt_a2a_peer_bindings", "trigger_keywords")
