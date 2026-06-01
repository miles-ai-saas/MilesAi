"""biz_service_line_template_packs

Revision ID: f2g8i6d5e347
Revises: e1f7h5c4d236
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "f2g8i6d5e347"
down_revision: Union[str, None] = "e1f7h5c4d236"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_service_line_template_packs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("service_line", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stages", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ai_config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("publisher_name", sa.String(length=128), nullable=False, server_default="Miles 官方"),
        sa.Column("publisher_type", sa.String(length=32), nullable=False, server_default="platform"),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("install_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_biz_sltp_service_line", "biz_service_line_template_packs", ["service_line"])
    op.create_index("idx_biz_sltp_active", "biz_service_line_template_packs", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_biz_sltp_active", table_name="biz_service_line_template_packs")
    op.drop_index("idx_biz_sltp_service_line", table_name="biz_service_line_template_packs")
    op.drop_table("biz_service_line_template_packs")
