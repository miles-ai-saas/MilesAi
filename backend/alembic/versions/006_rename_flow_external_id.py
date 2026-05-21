"""flow_flows.langflow_id 重命名为 external_flow_id（006 曾误用 flows 表名，008 兜底）

Revision ID: 006
Revises: 005
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(insp: sa.Inspector) -> list[str]:
    names = set(insp.get_table_names())
    out = []
    if "flow_flows" in names:
        out.append("flow_flows")
    if "flows" in names:
        out.append("flows")
    return out


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for table in _tables(insp):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "langflow_id" in cols and "external_flow_id" not in cols:
            op.alter_column(table, "langflow_id", new_column_name="external_flow_id")


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for table in _tables(insp):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "external_flow_id" in cols and "langflow_id" not in cols:
            op.alter_column(table, "external_flow_id", new_column_name="langflow_id")
