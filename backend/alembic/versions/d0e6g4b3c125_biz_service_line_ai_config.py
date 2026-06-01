"""biz_service_line_ai_config

Revision ID: d0e6g4b3c125
Revises: c9d5f3a2b014
Create Date: 2026-06-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d0e6g4b3c125"
down_revision: Union[str, None] = "c9d5f3a2b014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_service_line_templates",
        sa.Column("ai_config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("biz_service_line_templates", "ai_config")
