"""add deleted_at for soft delete

Revision ID: 004
Revises: 003
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.infra.db import Base
    from app.models.registry import load_all_models

    load_all_models()
    for table in Base.metadata.sorted_tables:
        if "deleted_at" not in table.c:
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{table.name}" '
                "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE"
            )
        )


def downgrade() -> None:
    from app.infra.db import Base
    from app.models.registry import load_all_models

    load_all_models()
    for table in reversed(Base.metadata.sorted_tables):
        if "deleted_at" not in table.c:
            continue
        op.execute(sa.text(f'ALTER TABLE "{table.name}" DROP COLUMN IF EXISTS deleted_at'))
