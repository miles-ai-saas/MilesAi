"""sys_categories 收敛为全平台全局字典（移除 tenant_id）

Revision ID: 010
Revises: 009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import column_exists, index_exists, table_exists

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _remap_category_fk(table: str) -> None:
    """将业务表 category_id 从租户副本对齐到平台行（按 domain+slug）。"""
    op.execute(
        sa.text(
            f"""
            UPDATE {table} r
            SET category_id = p.id
            FROM sys_categories t
            JOIN sys_categories p
              ON p.domain = t.domain AND p.slug = t.slug AND p.tenant_id IS NULL
            WHERE r.category_id = t.id
              AND t.tenant_id IS NOT NULL
            """
        )
    )


def _fallback_uncategorized(table: str, domain: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {table} r
            SET category_id = (
                SELECT id FROM sys_categories
                WHERE domain = :domain AND slug = 'uncategorized'
                LIMIT 1
            )
            WHERE r.category_id IS NOT NULL
              AND r.category_id NOT IN (SELECT id FROM sys_categories)
            """
        ).bindparams(domain=domain)
    )


def upgrade() -> None:
    if not table_exists("sys_categories"):
        return

    # 若仅有租户副本、尚无平台行：按 (domain, slug) 提升为平台行
    op.execute(
        sa.text(
            """
            INSERT INTO sys_categories (
                id, tenant_id, domain, name, slug, sort_order, is_system, created_at, updated_at
            )
            SELECT gen_random_uuid(), NULL, s.domain, s.name, s.slug, s.sort_order, TRUE, NOW(), NOW()
            FROM (
                SELECT DISTINCT ON (domain, slug) domain, name, slug, sort_order
                FROM sys_categories
                WHERE tenant_id IS NOT NULL
                ORDER BY domain, slug, sort_order
            ) s
            WHERE NOT EXISTS (
                SELECT 1 FROM sys_categories p
                WHERE p.tenant_id IS NULL AND p.domain = s.domain AND p.slug = s.slug
            )
            """
        )
    )

    for table in ("agt_agents", "prm_prompt_templates", "skl_skill_packages", "tool_tools"):
        if table_exists(table) and column_exists(table, "category_id"):
            _remap_category_fk(table)

    if table_exists("agt_agents"):
        _fallback_uncategorized("agt_agents", "agent")
    if table_exists("prm_prompt_templates"):
        _fallback_uncategorized("prm_prompt_templates", "prompt")
    if table_exists("skl_skill_packages"):
        _fallback_uncategorized("skl_skill_packages", "skill")
    if table_exists("tool_tools"):
        _fallback_uncategorized("tool_tools", "tool")

    op.execute(sa.text("DELETE FROM sys_categories WHERE tenant_id IS NOT NULL"))

    if index_exists("sys_categories", "uk_sys_categories_tenant_domain_slug"):
        op.drop_index("uk_sys_categories_tenant_domain_slug", table_name="sys_categories")
    if index_exists("sys_categories", "uk_sys_categories_platform_domain_slug"):
        op.drop_index("uk_sys_categories_platform_domain_slug", table_name="sys_categories")
    if index_exists("sys_categories", "idx_sys_categories_tenant_domain"):
        op.drop_index("idx_sys_categories_tenant_domain", table_name="sys_categories")

    op.drop_column("sys_categories", "tenant_id")

    if not index_exists("sys_categories", "uk_sys_categories_domain_slug"):
        op.create_index(
            "uk_sys_categories_domain_slug",
            "sys_categories",
            ["domain", "slug"],
            unique=True,
        )
    if not index_exists("sys_categories", "idx_sys_categories_domain"):
        op.create_index("idx_sys_categories_domain", "sys_categories", ["domain"])


def downgrade() -> None:
    if not table_exists("sys_categories"):
        return
    if index_exists("sys_categories", "uk_sys_categories_domain_slug"):
        op.drop_index("uk_sys_categories_domain_slug", table_name="sys_categories")
    if index_exists("sys_categories", "idx_sys_categories_domain"):
        op.drop_index("idx_sys_categories_domain", table_name="sys_categories")
    op.add_column(
        "sys_categories",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
    )
    if not index_exists("sys_categories", "uk_sys_categories_platform_domain_slug"):
        op.create_index(
            "uk_sys_categories_platform_domain_slug",
            "sys_categories",
            ["domain", "slug"],
            unique=True,
            postgresql_where=sa.text("tenant_id IS NULL"),
        )
