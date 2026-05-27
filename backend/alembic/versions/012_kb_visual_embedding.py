"""P1: 知识库 CLIP 视觉向量化模型绑定

Revision ID: 012
Revises: 011
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("kb_bases")}
    if "visual_embedding_model_config_id" not in columns:
        op.add_column(
            "kb_bases",
            sa.Column("visual_embedding_model_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("kb_bases")}
    if "visual_embedding_model_config_id" in columns:
        op.drop_column("kb_bases", "visual_embedding_model_config_id")
