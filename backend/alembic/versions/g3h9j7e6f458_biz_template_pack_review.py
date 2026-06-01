"""biz template pack review columns

Revision ID: g3h9j7e6f458
Revises: f2g8i6d5e347
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g3h9j7e6f458"
down_revision: Union[str, None] = "f2g8i6d5e347"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_service_line_template_packs",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
    )
    op.add_column("biz_service_line_template_packs", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("biz_service_line_template_packs", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("biz_service_line_template_packs", sa.Column("reviewed_by_admin_id", sa.UUID(), nullable=True))
    op.add_column("biz_service_line_template_packs", sa.Column("review_note", sa.Text(), nullable=True))
    op.create_index("idx_biz_sltp_status", "biz_service_line_template_packs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_biz_sltp_status", table_name="biz_service_line_template_packs")
    op.drop_column("biz_service_line_template_packs", "review_note")
    op.drop_column("biz_service_line_template_packs", "reviewed_by_admin_id")
    op.drop_column("biz_service_line_template_packs", "reviewed_at")
    op.drop_column("biz_service_line_template_packs", "submitted_at")
    op.drop_column("biz_service_line_template_packs", "status")
