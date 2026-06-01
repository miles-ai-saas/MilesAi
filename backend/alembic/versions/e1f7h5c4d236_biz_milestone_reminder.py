"""biz_milestone_reminder

Revision ID: e1f7h5c4d236
Revises: d0e6g4b3c125
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f7h5c4d236"
down_revision: Union[str, None] = "d0e6g4b3c125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("biz_milestones", sa.Column("due_reminder_sent_at", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("biz_milestones", "due_reminder_sent_at")
