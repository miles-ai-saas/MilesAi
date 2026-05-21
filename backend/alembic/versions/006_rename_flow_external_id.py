"""flows.langflow_id 重命名为 external_flow_id

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


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "flows" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("flows")}
    if "langflow_id" in cols and "external_flow_id" not in cols:
        op.alter_column("flows", "langflow_id", new_column_name="external_flow_id")


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "flows" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("flows")}
    if "external_flow_id" in cols and "langflow_id" not in cols:
        op.alter_column("flows", "external_flow_id", new_column_name="langflow_id")
