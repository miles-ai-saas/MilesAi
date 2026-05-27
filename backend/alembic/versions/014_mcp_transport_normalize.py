"""MCP transport 历史值 streamable-http 归一为 http。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tool_mcp_services" not in inspector.get_table_names():
        return
    op.execute(
        sa.text(
            "UPDATE tool_mcp_services SET transport = 'http' "
            "WHERE lower(transport) = 'streamable-http'"
        )
    )


def downgrade() -> None:
    pass
