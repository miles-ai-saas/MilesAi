"""media_assets 增加视频封面 attachment_id"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("media_assets")}
    if "cover_attachment_id" not in cols:
        op.add_column(
            "media_assets",
            sa.Column("cover_attachment_id", postgresql.UUID(as_uuid=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("media_assets", "cover_attachment_id")
