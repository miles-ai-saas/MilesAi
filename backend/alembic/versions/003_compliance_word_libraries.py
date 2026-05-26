"""合规词库：libraries / entries / bindings；迁移 cmp_sensitive_words 并删除旧表

Revision ID: 003
Revises: 002
Create Date: 2026-05-25
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_LIBRARY_NAME = "默认词库"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "cmp_word_libraries" not in inspector.get_table_names():
        op.create_table(
            "cmp_word_libraries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
            sa.UniqueConstraint("tenant_id", "name", name="un_cmp_word_libraries_tenant_name"),
        )
        op.create_index("idx_cmp_word_libraries_tenant_id", "cmp_word_libraries", ["tenant_id"])

    if "cmp_sensitive_word_entries" not in inspector.get_table_names():
        op.create_table(
            "cmp_sensitive_word_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("word", sa.String(128), nullable=False),
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
                "tenant_id", "word", name="un_cmp_sensitive_word_entries_tenant_word"
            ),
        )
        op.create_index(
            "idx_cmp_sensitive_word_entries_tenant_id",
            "cmp_sensitive_word_entries",
            ["tenant_id"],
        )

    if "cmp_library_word_bindings" not in inspector.get_table_names():
        op.create_table(
            "cmp_library_word_bindings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("library_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "action",
                postgresql.ENUM("warn", "block", name="sensitive_action", create_type=False),
                nullable=False,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
                "library_id", "entry_id", name="un_cmp_library_word_bindings_lib_entry"
            ),
        )
        op.create_index(
            "idx_cmp_library_word_bindings_library_id",
            "cmp_library_word_bindings",
            ["library_id"],
        )
        op.create_index(
            "idx_cmp_library_word_bindings_entry_id",
            "cmp_library_word_bindings",
            ["entry_id"],
        )

    if "cmp_compliance_library_bindings" not in inspector.get_table_names():
        op.create_table(
            "cmp_compliance_library_bindings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("library_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("scope", sa.String(32), nullable=False, server_default="tenant"),
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
                "library_id",
                "scope",
                name="un_cmp_compliance_library_bindings_tenant_lib_scope",
            ),
        )
        op.create_index(
            "idx_cmp_compliance_library_bindings_tenant_id",
            "cmp_compliance_library_bindings",
            ["tenant_id"],
        )

    if "cmp_sensitive_words" in inspector.get_table_names():
        _migrate_legacy_sensitive_words(bind)

    inspector = sa.inspect(bind)
    if "cmp_sensitive_words" in inspector.get_table_names():
        op.drop_index("un_cmp_sensitive_words_tenant_id_word", table_name="cmp_sensitive_words")
        op.drop_index("idx_cmp_sensitive_words_tenant_id", table_name="cmp_sensitive_words")
        op.drop_table("cmp_sensitive_words")


def _migrate_legacy_sensitive_words(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, word, category, action, is_active, created_at, updated_at, deleted_at
            FROM cmp_sensitive_words
            ORDER BY tenant_id, word, created_at
            """
        )
    ).fetchall()
    if not rows:
        return

    libraries: dict = {}
    entries: dict = {}
    now = datetime.now(timezone.utc)

    for row in rows:
        tid = str(row.tenant_id)
        word = (row.word or "").strip()
        if not word:
            continue
        if tid not in libraries:
            lib_id = uuid4()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO cmp_word_libraries
                    (id, tenant_id, name, description, is_active, sort_order, created_at, updated_at, deleted_at)
                    VALUES (:id, :tenant_id, :name, NULL, true, 0, :now, :now, NULL)
                    """
                ),
                {"id": lib_id, "tenant_id": row.tenant_id, "name": DEFAULT_LIBRARY_NAME, "now": now},
            )
            bind.execute(
                sa.text(
                    """
                    INSERT INTO cmp_compliance_library_bindings
                    (id, tenant_id, library_id, scope, created_at, updated_at, deleted_at)
                    VALUES (:id, :tenant_id, :library_id, 'tenant', :now, :now, NULL)
                    """
                ),
                {"id": uuid4(), "tenant_id": row.tenant_id, "library_id": lib_id, "now": now},
            )
            libraries[tid] = lib_id

        lib_id = libraries[tid]
        entry_key = (tid, word.lower())
        if entry_key not in entries:
            entry_id = uuid4()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO cmp_sensitive_word_entries
                    (id, tenant_id, word, created_at, updated_at, deleted_at)
                    VALUES (:id, :tenant_id, :word, :now, :now, :deleted_at)
                    ON CONFLICT (tenant_id, word) DO NOTHING
                    """
                ),
                {
                    "id": entry_id,
                    "tenant_id": row.tenant_id,
                    "word": word,
                    "now": now,
                    "deleted_at": row.deleted_at,
                },
            )
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM cmp_sensitive_word_entries WHERE tenant_id = :tid AND word = :word"
                ),
                {"tid": row.tenant_id, "word": word},
            ).scalar()
            entries[entry_key] = existing or entry_id

        entry_id = entries[entry_key]
        action = row.action if row.action in ("warn", "block") else "warn"
        bind.execute(
            sa.text(
                """
                INSERT INTO cmp_library_word_bindings
                (id, library_id, entry_id, action, is_active, created_at, updated_at, deleted_at)
                VALUES (:id, :library_id, :entry_id, :action, :is_active, :now, :now, :deleted_at)
                ON CONFLICT (library_id, entry_id) DO NOTHING
                """
            ),
            {
                "id": uuid4(),
                "library_id": lib_id,
                "entry_id": entry_id,
                "action": action,
                "is_active": bool(row.is_active),
                "now": now,
                "deleted_at": row.deleted_at,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "cmp_sensitive_words" not in inspector.get_table_names():
        op.create_table(
            "cmp_sensitive_words",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("word", sa.String(128), nullable=False),
            sa.Column("category", sa.String(64), nullable=True),
            sa.Column(
                "action",
                postgresql.ENUM("warn", "block", name="sensitive_action", create_type=False),
                nullable=False,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        )
        op.create_index("idx_cmp_sensitive_words_tenant_id", "cmp_sensitive_words", ["tenant_id"])
        op.create_index(
            "un_cmp_sensitive_words_tenant_id_word",
            "cmp_sensitive_words",
            ["tenant_id", "word"],
            unique=True,
        )

    for table in (
        "cmp_compliance_library_bindings",
        "cmp_library_word_bindings",
        "cmp_sensitive_word_entries",
        "cmp_word_libraries",
    ):
        if table in inspector.get_table_names():
            op.drop_table(table)
