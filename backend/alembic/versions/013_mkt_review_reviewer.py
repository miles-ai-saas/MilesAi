"""mkt_apps 审核人字段扩展。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "mkt_apps" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("mkt_apps")}
    if "reviewed_by_admin_id" not in cols:
        op.add_column(
            "mkt_apps",
            sa.Column("reviewed_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "reviewer_type" not in cols:
        op.add_column("mkt_apps", sa.Column("reviewer_type", sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "mkt_apps" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("mkt_apps")}
    if "reviewer_type" in cols:
        op.drop_column("mkt_apps", "reviewer_type")
    if "reviewed_by_admin_id" in cols:
        op.drop_column("mkt_apps", "reviewed_by_admin_id")
