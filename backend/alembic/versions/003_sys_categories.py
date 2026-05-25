"""sys_categories 与 agent/prompt category_id

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migration_helpers import (
    add_column_if_missing,
    create_index_if_missing,
    drop_column_if_exists,
    table_exists,
)

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("sys_categories"):
        op.create_table(
            "sys_categories",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("domain", sa.String(32), nullable=False),
            sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
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
            sa.UniqueConstraint(
                "tenant_id",
                "domain",
                "slug",
                name="uk_sys_categories_tenant_domain_slug",
            ),
        )
        create_index_if_missing(
            "idx_sys_categories_tenant_domain",
            "sys_categories",
            ["tenant_id", "domain"],
        )

    add_column_if_missing(
        "agt_agents",
        sa.Column("category_id", UUID(as_uuid=True), nullable=True),
    )
    create_index_if_missing(
        "idx_agt_agents_category_id",
        "agt_agents",
        ["category_id"],
    )

    add_column_if_missing(
        "prm_prompt_templates",
        sa.Column("category_id", UUID(as_uuid=True), nullable=True),
    )
    create_index_if_missing(
        "idx_prm_prompt_templates_category_id",
        "prm_prompt_templates",
        ["category_id"],
    )


def downgrade() -> None:
    drop_column_if_exists("prm_prompt_templates", "category_id")
    drop_column_if_exists("agt_agents", "category_id")
    if table_exists("sys_categories"):
        op.drop_table("sys_categories")
