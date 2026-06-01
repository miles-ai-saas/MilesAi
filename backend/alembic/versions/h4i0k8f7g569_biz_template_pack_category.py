"""biz template pack category

Revision ID: h4i0k8f7g569
Revises: g3h9j7e6f458
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h4i0k8f7g569"
down_revision: Union[str, None] = "g3h9j7e6f458"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "biz_service_line_template_packs",
        sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
    )
    op.create_index("idx_biz_sltp_category", "biz_service_line_template_packs", ["category"])
    op.execute(
        """
        UPDATE biz_service_line_template_packs SET category = CASE service_line
            WHEN 'brand_identity' THEN 'brand'
            WHEN 'video_production' THEN 'video'
            WHEN 'exhibition' THEN 'exhibition'
            WHEN 'event' THEN 'event'
            WHEN 'training' THEN 'training'
            WHEN 'signage' THEN 'signage'
            WHEN 'cultural_product' THEN 'cultural'
            WHEN 'print' THEN 'print'
            ELSE 'general'
        END
        """
    )
    op.alter_column("biz_service_line_template_packs", "category", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_biz_sltp_category", table_name="biz_service_line_template_packs")
    op.drop_column("biz_service_line_template_packs", "category")
