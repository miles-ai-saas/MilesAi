"""移除 flow_flows.external_flow_id（原外部流程 ID 预留列）

Revision ID: 017
Revises: 016
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _flow_table_names(insp: sa.Inspector) -> list[str]:
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
    for table in _flow_table_names(insp):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "external_flow_id" in cols:
            op.drop_column(table, "external_flow_id")


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for table in _flow_table_names(insp):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "external_flow_id" not in cols:
            op.add_column(
                table,
                sa.Column("external_flow_id", sa.String(length=64), nullable=True),
            )
