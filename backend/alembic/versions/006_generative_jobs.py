"""生成任务表 generative_jobs（异步生视频等）

Revision ID: 006
Revises: 005
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "generative_jobs" in inspector.get_table_names():
        return

    op.create_table(
        "generative_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "success",
                "failed",
                name="generative_job_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_ref_type", sa.String(32), nullable=True),
        sa.Column("source_ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("progress_message", sa.String(256), nullable=True),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
    )
    op.create_index("idx_generative_jobs_tenant_id", "generative_jobs", ["tenant_id"])
    op.create_index("idx_generative_jobs_status", "generative_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_generative_jobs_status", table_name="generative_jobs")
    op.drop_index("idx_generative_jobs_tenant_id", table_name="generative_jobs")
    op.drop_table("generative_jobs")
    op.execute("DROP TYPE IF EXISTS generative_job_status")
