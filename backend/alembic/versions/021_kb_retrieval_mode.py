"""知识库检索模式：vector / hybrid

Revision ID: 021
Revises: 020
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kb_bases",
        sa.Column(
            "retrieval_mode",
            sa.String(16),
            nullable=False,
            server_default="vector",
        ),
    )
    op.add_column(
        "kb_bases",
        sa.Column(
            "hybrid_alpha",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
    )


def downgrade() -> None:
    op.drop_column("kb_bases", "hybrid_alpha")
    op.drop_column("kb_bases", "retrieval_mode")
