"""钩子表：hook_definitions / hook_bindings（从 cmp_hook_* 迁移或新建）

Revision ID: 003
Revises: 002
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HOOK_TRIGGER = sa.Enum(
    "before_call",
    "after_call",
    "before_reasoning",
    "after_reasoning",
    "before_tool",
    "after_tool",
    "on_error",
    name="hook_trigger",
    create_type=True,
)
HOOK_TYPE = sa.Enum("http", "python", name="hook_type", create_type=True)
HOOK_SCOPE = sa.Enum("global", "agent", "flow", "tool", "app", name="hook_scope", create_type=True)


def _ensure_hook_trigger_enum(bind) -> None:
    HOOK_TRIGGER.create(bind, checkfirst=True)


def _ensure_all_hook_enums(bind) -> None:
    HOOK_TYPE.create(bind, checkfirst=True)
    HOOK_SCOPE.create(bind, checkfirst=True)
    _ensure_hook_trigger_enum(bind)


def _create_hook_tables() -> None:
    op.create_table(
        "hook_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("hook_type", HOOK_TYPE, nullable=False),
        sa.Column("config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_hook_definitions_tenant_id", "hook_definitions", ["tenant_id"])

    op.create_table(
        "hook_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hook_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scope", HOOK_SCOPE, nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trigger", HOOK_TRIGGER, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_hook_bindings_tenant_id", "hook_bindings", ["tenant_id"])
    op.create_index("idx_hook_bindings_hook_id", "hook_bindings", ["hook_id"])
    op.create_index(
        "un_hook_bindings_hook_scope_target_trigger",
        "hook_bindings",
        ["hook_id", "scope", "target_id", "trigger"],
        unique=True,
    )


def _migrate_from_cmp() -> None:
    """cmp_hook_* → hook_*，phase → trigger。"""
    bind = op.get_bind()
    _ensure_hook_trigger_enum(bind)
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE hook_scope ADD VALUE IF NOT EXISTS 'tool';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.rename_table("cmp_hook_definitions", "hook_definitions")
    op.rename_table("cmp_hook_bindings", "hook_bindings")

    op.add_column(
        "hook_bindings",
        sa.Column("trigger", HOOK_TRIGGER, nullable=True),
    )
    op.execute(
        """
        UPDATE hook_bindings SET trigger = CASE
            WHEN phase::text = 'pre' THEN 'before_call'::hook_trigger
            WHEN phase::text = 'post' THEN 'after_call'::hook_trigger
            ELSE 'before_call'::hook_trigger
        END
        """
    )
    op.alter_column("hook_bindings", "trigger", nullable=False)
    op.drop_column("hook_bindings", "phase")

    # 旧唯一索引名可能仍带 cmp_ 前缀，重建为当前命名
    op.execute("DROP INDEX IF EXISTS un_cmp_hook_bindings_hook_id_scope_target")
    op.execute("DROP INDEX IF EXISTS un_cmp_hook_bindings_hook_id_scope_target_id")
    op.create_index(
        "un_hook_bindings_hook_scope_target_trigger",
        "hook_bindings",
        ["hook_id", "scope", "target_id", "trigger"],
        unique=True,
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "hook_definitions" in tables:
        return

    if "cmp_hook_definitions" in tables and "cmp_hook_bindings" in tables:
        _migrate_from_cmp()
        return

    _ensure_all_hook_enums(bind)
    _create_hook_tables()


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "hook_definitions" in tables:
        op.drop_table("hook_bindings")
        op.drop_table("hook_definitions")
