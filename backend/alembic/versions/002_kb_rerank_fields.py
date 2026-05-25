"""KB rerank 字段

Revision ID: 002
Revises: 001
Create Date: 2026-05-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kb_bases",
        sa.Column("rerank_model_config_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "kb_bases",
        sa.Column(
            "rerank_candidate_k",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )


def downgrade() -> None:
    op.drop_column("kb_bases", "rerank_candidate_k")
    op.drop_column("kb_bases", "rerank_model_config_id")
