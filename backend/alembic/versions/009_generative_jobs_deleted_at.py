"""generative_jobs 增加 deleted_at（与 TimestampMixin 对齐）

Revision ID: 009
Revises: 008
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "generative_jobs" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("generative_jobs")}
    if "deleted_at" not in cols:
        op.add_column(
            "generative_jobs",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "generative_jobs" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("generative_jobs")}
    if "deleted_at" in cols:
        op.drop_column("generative_jobs", "deleted_at")
