"""Hook 执行日志 trace_id 索引

Revision ID: 005
Revises: 004
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_hook_execution_logs_tenant_trace",
        "hook_execution_logs",
        ["tenant_id", "trace_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_hook_execution_logs_tenant_trace", table_name="hook_execution_logs")
