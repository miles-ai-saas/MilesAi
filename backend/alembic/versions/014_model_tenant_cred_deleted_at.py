"""agt_model_tenant_credentials 补 deleted_at（与 TimestampMixin 一致）

Revision ID: 014
Revises: 013
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    if _col_exists("agt_model_tenant_credentials", "deleted_at"):
        return
    op.add_column(
        "agt_model_tenant_credentials",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    if not _col_exists("agt_model_tenant_credentials", "deleted_at"):
        return
    op.drop_column("agt_model_tenant_credentials", "deleted_at")
