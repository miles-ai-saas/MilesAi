"""P1: 定时任务执行历史 + 市场应用 visibility

Revision ID: 010
Revises: 009
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agt_schedule_runs" not in tables:
        op.create_table(
            "agt_schedule_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
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
        op.create_index(
            "idx_agt_schedule_runs_schedule_id", "agt_schedule_runs", ["schedule_id"]
        )
        op.create_index(
            "idx_agt_schedule_runs_tenant_id", "agt_schedule_runs", ["tenant_id"]
        )

    if "mkt_apps" in tables:
        cols = {c["name"] for c in inspector.get_columns("mkt_apps")}
        if "visibility" not in cols:
            op.add_column(
                "mkt_apps",
                sa.Column(
                    "visibility",
                    sa.String(32),
                    nullable=False,
                    server_default="public",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "mkt_apps" in tables:
        cols = {c["name"] for c in inspector.get_columns("mkt_apps")}
        if "visibility" in cols:
            op.drop_column("mkt_apps", "visibility")

    if "agt_schedule_runs" in tables:
        op.drop_index("idx_agt_schedule_runs_tenant_id", table_name="agt_schedule_runs")
        op.drop_index("idx_agt_schedule_runs_schedule_id", table_name="agt_schedule_runs")
        op.drop_table("agt_schedule_runs")
