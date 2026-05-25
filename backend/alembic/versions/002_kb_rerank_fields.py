"""KB rerank 字段

Revision ID: 002
Revises: 001
Create Date: 2026-05-24

001 使用 create_all 会按当前 ORM 建表；若 rerank 字段已存在则跳过（见 migration_helpers）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from migration_helpers import add_column_if_missing, drop_column_if_exists

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    add_column_if_missing(
        "kb_bases",
        sa.Column("rerank_model_config_id", UUID(as_uuid=True), nullable=True),
    )
    add_column_if_missing(
        "kb_bases",
        sa.Column(
            "rerank_candidate_k",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )


def downgrade() -> None:
    drop_column_if_exists("kb_bases", "rerank_candidate_k")
    drop_column_if_exists("kb_bases", "rerank_model_config_id")
