"""应用市场审核与评分

Revision ID: 005
Revises: 004
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TYPE marketplace_app_status ADD VALUE IF NOT EXISTS 'pending_review'"
        )
    )
    op.execute(
        sa.text("ALTER TYPE marketplace_app_status ADD VALUE IF NOT EXISTS 'rejected'")
    )

    op.add_column(
        "mkt_apps",
        sa.Column("rating_avg", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "mkt_apps",
        sa.Column("rating_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "mkt_apps",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mkt_apps",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mkt_apps",
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("mkt_apps", sa.Column("review_note", sa.Text(), nullable=True))

    op.create_table(
        "mkt_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "app_id",
            "user_id",
            name="uk_mkt_ratings_tenant_app_user",
        ),
    )
    op.create_index("idx_mkt_ratings_app_id", "mkt_ratings", ["app_id"])


def downgrade() -> None:
    op.drop_index("idx_mkt_ratings_app_id", table_name="mkt_ratings")
    op.drop_table("mkt_ratings")
    op.drop_column("mkt_apps", "review_note")
    op.drop_column("mkt_apps", "reviewed_by")
    op.drop_column("mkt_apps", "reviewed_at")
    op.drop_column("mkt_apps", "submitted_at")
    op.drop_column("mkt_apps", "rating_count")
    op.drop_column("mkt_apps", "rating_avg")
