"""应用安装快照表（市场回滚）

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mkt_install_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("install_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("resources", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_mkt_install_snapshots_install_id", "mkt_install_snapshots", ["install_id"])
    op.create_index("idx_mkt_install_snapshots_tenant_id", "mkt_install_snapshots", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("idx_mkt_install_snapshots_tenant_id", table_name="mkt_install_snapshots")
    op.drop_index("idx_mkt_install_snapshots_install_id", table_name="mkt_install_snapshots")
    op.drop_table("mkt_install_snapshots")
