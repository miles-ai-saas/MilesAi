"""知识库向量化改为绑定 agt_model_configs

Revision ID: 019
Revises: 018
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kb_bases",
        sa.Column("embedding_model_config_id", UUID(as_uuid=True), nullable=True),
    )
    for col in ("embedding_profile", "embedding_backend", "embedding_model_name"):
        try:
            op.drop_column("kb_bases", col)
        except Exception:
            pass


def downgrade() -> None:
    op.add_column(
        "kb_bases",
        sa.Column("embedding_profile", sa.String(64), server_default="local-bge-zh"),
    )
    op.add_column(
        "kb_bases",
        sa.Column("embedding_backend", sa.String(32), server_default="local"),
    )
    op.add_column(
        "kb_bases",
        sa.Column(
            "embedding_model_name",
            sa.String(256),
            server_default="BAAI/bge-base-zh-v1.5",
        ),
    )
    op.drop_column("kb_bases", "embedding_model_config_id")
