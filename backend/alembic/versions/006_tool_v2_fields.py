"""tool_tools v2：slug、分类、参数 schema

Revision ID: 006
Revises: 005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migration_helpers import (
    add_column_if_missing,
    column_exists,
    create_index_if_missing,
    drop_column_if_exists,
    index_exists,
    table_exists,
)

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("tool_tools"):
        return

    add_column_if_missing(
        "tool_tools",
        sa.Column("slug", sa.String(64), nullable=True),
    )
    add_column_if_missing(
        "tool_tools",
        sa.Column("category_id", UUID(as_uuid=True), nullable=True),
    )
    add_column_if_missing(
        "tool_tools",
        sa.Column("version", sa.String(16), server_default="1.0.0", nullable=False),
    )
    add_column_if_missing(
        "tool_tools",
        sa.Column("require_confirmation", sa.Boolean(), server_default="false", nullable=False),
    )
    add_column_if_missing(
        "tool_tools",
        sa.Column("parameters", JSONB(), server_default="[]", nullable=False),
    )

    if column_exists("tool_tools", "slug"):
        op.execute(
            """
            UPDATE tool_tools
            SET slug = lower(regexp_replace(regexp_replace(trim(name), '[^a-zA-Z0-9]+', '_', 'g'), '^_+|_+$', '', 'g'))
            WHERE slug IS NULL OR slug = ''
            """
        )
        op.execute(
            """
            UPDATE tool_tools SET slug = 'tool_' || substr(replace(id::text, '-', ''), 1, 8)
            WHERE slug IS NULL OR slug = '' OR slug !~ '^[a-z][a-z0-9_]*$'
            """
        )
        op.alter_column("tool_tools", "slug", nullable=False)

    if index_exists("tool_tools", "un_tool_tools_tenant_id_name"):
        op.drop_index("un_tool_tools_tenant_id_name", table_name="tool_tools")

    create_index_if_missing(
        "un_tool_tools_tenant_id_slug",
        "tool_tools",
        ["tenant_id", "slug"],
        unique=True,
    )

    # 扩展 tool_type enum：script（若 enum 已存在）
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE tool_type ADD VALUE IF NOT EXISTS 'script';
        EXCEPTION
            WHEN duplicate_object THEN null;
            WHEN undefined_object THEN null;
        END $$;
        """
    )


def downgrade() -> None:
    if not table_exists("tool_tools"):
        return

    drop_column_if_exists("tool_tools", "parameters")
    drop_column_if_exists("tool_tools", "require_confirmation")
    drop_column_if_exists("tool_tools", "version")
    drop_column_if_exists("tool_tools", "category_id")
    drop_column_if_exists("tool_tools", "slug")

    if index_exists("tool_tools", "un_tool_tools_tenant_id_slug"):
        op.drop_index("un_tool_tools_tenant_id_slug", table_name="tool_tools")

    create_index_if_missing(
        "un_tool_tools_tenant_id_name",
        "tool_tools",
        ["tenant_id", "name"],
        unique=True,
    )
