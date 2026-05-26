"""generative_jobs：进度百分比与 cancelled 状态

Revision ID: 007
Revises: 006
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("generative_jobs")}
    if "progress_percent" not in cols:
        op.add_column(
            "generative_jobs",
            sa.Column("progress_percent", sa.Integer(), nullable=True),
        )
    op.execute("ALTER TYPE generative_job_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    op.drop_column("generative_jobs", "progress_percent")
    # PostgreSQL 枚举值无法安全删除 cancelled，保留
