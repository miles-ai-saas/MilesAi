"""智能体定时任务表 agt_schedules

Revision ID: 002
Revises: 001
Create Date: 2026-05-25

在已执行 001 的环境上补建表；新环境 001 的 create_all 已含本表时本迁移会跳过。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "agt_schedules" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "agt_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cron", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_agt_schedules_tenant_id", "agt_schedules", ["tenant_id"])
    op.create_index("idx_agt_schedules_agent_id", "agt_schedules", ["agent_id"])
    op.create_index("idx_agt_schedules_next_run_at", "agt_schedules", ["next_run_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if "agt_schedules" not in sa.inspect(bind).get_table_names():
        return
    op.drop_index("idx_agt_schedules_next_run_at", table_name="agt_schedules")
    op.drop_index("idx_agt_schedules_agent_id", table_name="agt_schedules")
    op.drop_index("idx_agt_schedules_tenant_id", table_name="agt_schedules")
    op.drop_table("agt_schedules")
