"""sys_categories 支持平台内置（tenant_id 可空）

Revision ID: 008
Revises: 007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import index_exists, table_exists

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("sys_categories"):
        return
    op.alter_column("sys_categories", "tenant_id", existing_type=sa.UUID(), nullable=True)
    try:
        op.drop_constraint("uk_sys_categories_tenant_domain_slug", "sys_categories", type_="unique")
    except Exception:
        pass
    if not index_exists("sys_categories", "uk_sys_categories_platform_domain_slug"):
        op.create_index(
            "uk_sys_categories_platform_domain_slug",
            "sys_categories",
            ["domain", "slug"],
            unique=True,
            postgresql_where=sa.text("tenant_id IS NULL"),
        )
    if not index_exists("sys_categories", "uk_sys_categories_tenant_domain_slug"):
        op.create_index(
            "uk_sys_categories_tenant_domain_slug",
            "sys_categories",
            ["tenant_id", "domain", "slug"],
            unique=True,
            postgresql_where=sa.text("tenant_id IS NOT NULL"),
        )


def downgrade() -> None:
    if not table_exists("sys_categories"):
        return
    if index_exists("sys_categories", "uk_sys_categories_tenant_domain_slug"):
        op.drop_index("uk_sys_categories_tenant_domain_slug", table_name="sys_categories")
    if index_exists("sys_categories", "uk_sys_categories_platform_domain_slug"):
        op.drop_index("uk_sys_categories_platform_domain_slug", table_name="sys_categories")
    op.create_unique_constraint(
        "uk_sys_categories_tenant_domain_slug",
        "sys_categories",
        ["tenant_id", "domain", "slug"],
    )
    op.alter_column("sys_categories", "tenant_id", existing_type=sa.UUID(), nullable=False)
