"""生成任务与工具调用日志添加 trace_id

Revision ID: 007
Revises: h4i0k8f7g569
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "h4i0k8f7g569"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # generative_jobs: 添加 trace_id 列与索引
    op.add_column(
        "generative_jobs",
        sa.Column("trace_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "idx_generative_jobs_trace_id",
        "generative_jobs",
        ["trace_id"],
    )

    # tool_invocation_logs: 添加 trace_id 列与索引
    op.add_column(
        "tool_invocation_logs",
        sa.Column("trace_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "idx_tool_invocation_logs_trace_id",
        "tool_invocation_logs",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tool_invocation_logs_trace_id", table_name="tool_invocation_logs")
    op.drop_column("tool_invocation_logs", "trace_id")
    op.drop_index("idx_generative_jobs_trace_id", table_name="generative_jobs")
    op.drop_column("generative_jobs", "trace_id")
