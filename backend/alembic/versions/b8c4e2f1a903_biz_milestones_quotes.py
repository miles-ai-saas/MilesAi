"""biz_milestones_quotes

Revision ID: b8c4e2f1a903
Revises: a54ef067f04a
Create Date: 2026-06-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8c4e2f1a903"
down_revision: Union[str, None] = "a54ef067f04a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_milestones",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("work_package_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_biz_ms_tenant", "biz_milestones", ["tenant_id"], unique=False)
    op.create_index("idx_biz_ms_wp", "biz_milestones", ["tenant_id", "work_package_id"], unique=False)
    op.create_index("idx_biz_ms_project", "biz_milestones", ["tenant_id", "project_id"], unique=False)

    op.create_table(
        "biz_quotes",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_biz_quotes_tenant", "biz_quotes", ["tenant_id"], unique=False)
    op.create_index("idx_biz_quotes_opp", "biz_quotes", ["tenant_id", "opportunity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_biz_quotes_opp", table_name="biz_quotes")
    op.drop_index("idx_biz_quotes_tenant", table_name="biz_quotes")
    op.drop_table("biz_quotes")
    op.drop_index("idx_biz_ms_project", table_name="biz_milestones")
    op.drop_index("idx_biz_ms_wp", table_name="biz_milestones")
    op.drop_index("idx_biz_ms_tenant", table_name="biz_milestones")
    op.drop_table("biz_milestones")
