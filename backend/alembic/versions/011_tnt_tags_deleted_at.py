"""tnt_tags 补齐 deleted_at（与 TimestampMixin 一致）

Revision ID: 011
Revises: 010
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists, table_exists

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("tnt_tags") and not column_exists("tnt_tags", "deleted_at"):
        op.add_column(
            "tnt_tags",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if table_exists("tnt_tags") and column_exists("tnt_tags", "deleted_at"):
        op.drop_column("tnt_tags", "deleted_at")
