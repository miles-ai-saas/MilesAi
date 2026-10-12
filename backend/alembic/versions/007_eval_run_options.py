"""eval_runs 增加 options（JSONB，Judge 模型等）

Revision ID: 007
Revises: 006
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE eval_runs "
        "ADD COLUMN IF NOT EXISTS options JSONB NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE eval_runs DROP COLUMN IF EXISTS options")
