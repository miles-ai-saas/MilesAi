"""知识库检索日志与租户附件表

Revision ID: 020
Revises: 019
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kb_search_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kb_ids", JSONB, nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_mode", sa.String(32), nullable=False, server_default="vector"),
        sa.Column("source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_kb_search_logs_tenant_created", "kb_search_logs", ["tenant_id", "created_at"])
    op.create_index("idx_kb_search_logs_kb_created", "kb_search_logs", ["kb_id", "created_at"])

    op.create_table(
        "sys_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("object_bucket", sa.String(128), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False, server_default="general"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
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
    op.create_index("idx_sys_attachments_tenant_id", "sys_attachments", ["tenant_id"])
    op.create_index(
        "idx_sys_attachments_resource",
        "sys_attachments",
        ["tenant_id", "resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_table("sys_attachments")
    op.drop_table("kb_search_logs")
