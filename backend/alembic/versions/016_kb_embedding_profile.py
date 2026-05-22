"""kb_bases 增加向量化规格字段（profile / backend / model_name）

Revision ID: 016
Revises: 015
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _col_exists("kb_bases", "embedding_profile"):
        op.add_column(
            "kb_bases",
            sa.Column(
                "embedding_profile",
                sa.String(64),
                nullable=False,
                server_default="local-minilm",
            ),
        )
    if not _col_exists("kb_bases", "embedding_backend"):
        op.add_column(
            "kb_bases",
            sa.Column(
                "embedding_backend",
                sa.String(32),
                nullable=False,
                server_default="local",
            ),
        )
    if not _col_exists("kb_bases", "embedding_model_name"):
        op.add_column(
            "kb_bases",
            sa.Column(
                "embedding_model_name",
                sa.String(256),
                nullable=False,
                server_default="sentence-transformers/all-MiniLM-L6-v2",
            ),
        )


def downgrade() -> None:
    if _col_exists("kb_bases", "embedding_model_name"):
        op.drop_column("kb_bases", "embedding_model_name")
    if _col_exists("kb_bases", "embedding_backend"):
        op.drop_column("kb_bases", "embedding_backend")
    if _col_exists("kb_bases", "embedding_profile"):
        op.drop_column("kb_bases", "embedding_profile")
