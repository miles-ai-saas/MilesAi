"""技能包 v2：分类、slug、来源、文件存储路径

Revision ID: 005
Revises: 004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migration_helpers import (
    add_column_if_missing,
    column_exists,
    create_index_if_missing,
    drop_column_if_exists,
    index_exists,
    table_exists,
)

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("skl_skill_packages"):
        return

    add_column_if_missing(
        "skl_skill_packages",
        sa.Column("category_id", UUID(as_uuid=True), nullable=True),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column("slug", sa.String(128), nullable=True),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column("source_type", sa.String(32), nullable=False, server_default="manual"),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column("storage_path", sa.String(512), nullable=True),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    add_column_if_missing(
        "skl_skill_packages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    bind = op.get_bind()
    if column_exists("skl_skill_packages", "slug"):
        bind.execute(
            sa.text(
                """
                UPDATE skl_skill_packages
                SET slug = regexp_replace(lower(trim(name)), '[^a-z0-9]+', '_', 'g')
                WHERE slug IS NULL OR slug = ''
                """
            )
        )
        bind.execute(
            sa.text(
                """
                UPDATE skl_skill_packages s
                SET slug = 'skill_' || substr(replace(s.id::text, '-', ''), 1, 12)
                WHERE slug IS NULL OR slug = ''
                """
            )
        )

    op.alter_column("skl_skill_packages", "slug", nullable=False, existing_type=sa.String(128))

    create_index_if_missing(
        "idx_skl_skill_packages_category",
        "skl_skill_packages",
        ["tenant_id", "category_id"],
    )
    create_index_if_missing(
        "uk_skl_skill_packages_tenant_slug",
        "skl_skill_packages",
        ["tenant_id", "slug"],
        unique=True,
    )

    if index_exists("skl_skill_packages", "un_skl_skill_packages_tenant_id_name"):
        op.drop_index("un_skl_skill_packages_tenant_id_name", table_name="skl_skill_packages")
    create_index_if_missing(
        "idx_skl_skill_packages_tenant_name",
        "skl_skill_packages",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    if not table_exists("skl_skill_packages"):
        return
    if index_exists("skl_skill_packages", "uk_skl_skill_packages_tenant_slug"):
        op.drop_index("uk_skl_skill_packages_tenant_slug", table_name="skl_skill_packages")
    if index_exists("skl_skill_packages", "idx_skl_skill_packages_category"):
        op.drop_index("idx_skl_skill_packages_category", table_name="skl_skill_packages")
    if index_exists("skl_skill_packages", "idx_skl_skill_packages_tenant_name"):
        op.drop_index("idx_skl_skill_packages_tenant_name", table_name="skl_skill_packages")
    drop_column_if_exists("skl_skill_packages", "category_id")
    drop_column_if_exists("skl_skill_packages", "slug")
    drop_column_if_exists("skl_skill_packages", "source_type")
    drop_column_if_exists("skl_skill_packages", "storage_path")
