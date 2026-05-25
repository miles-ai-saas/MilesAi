"""租户全局标签与实体绑定

Revision ID: 009
Revises: 008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migration_helpers import index_exists, table_exists

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not table_exists("tnt_tags"):
        op.create_table(
            "tnt_tags",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not index_exists("tnt_tags", "uk_tnt_tags_tenant_slug"):
        op.create_index(
            "uk_tnt_tags_tenant_slug",
            "tnt_tags",
            ["tenant_id", "slug"],
            unique=True,
        )
    if not index_exists("tnt_tags", "idx_tnt_tags_tenant_id"):
        op.create_index("idx_tnt_tags_tenant_id", "tnt_tags", ["tenant_id"])

    if not table_exists("tnt_entity_tag_bindings"):
        op.create_table(
            "tnt_entity_tag_bindings",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("entity_type", sa.String(32), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
            sa.Column("tag_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if not index_exists("tnt_entity_tag_bindings", "uk_tnt_entity_tag_bindings"):
        op.create_index(
            "uk_tnt_entity_tag_bindings",
            "tnt_entity_tag_bindings",
            ["entity_type", "entity_id", "tag_id"],
            unique=True,
        )
    if not index_exists("tnt_entity_tag_bindings", "idx_tnt_entity_tag_bindings_tenant"):
        op.create_index(
            "idx_tnt_entity_tag_bindings_tenant",
            "tnt_entity_tag_bindings",
            ["tenant_id", "entity_type", "entity_id"],
        )
    if not index_exists("tnt_entity_tag_bindings", "idx_tnt_entity_tag_bindings_tag"):
        op.create_index(
            "idx_tnt_entity_tag_bindings_tag",
            "tnt_entity_tag_bindings",
            ["tenant_id", "tag_id"],
        )

    if table_exists("sys_categories"):
        op.execute(
            "UPDATE sys_categories SET is_system = true WHERE tenant_id IS NOT NULL AND is_system = false"
        )


def downgrade() -> None:
    if table_exists("tnt_entity_tag_bindings"):
        op.drop_table("tnt_entity_tag_bindings")
    if table_exists("tnt_tags"):
        op.drop_table("tnt_tags")
