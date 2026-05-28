"""租户对象存储 BYOK 配置表

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sys_tenant_object_storage",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("endpoint", sa.String(255), nullable=False, server_default=""),
        sa.Column("bucket", sa.String(128), nullable=False, server_default=""),
        sa.Column("access_key", sa.String(128), nullable=False, server_default=""),
        sa.Column("secret_key_encrypted", sa.String(512), nullable=False, server_default=""),
        sa.Column("secure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("region", sa.String(64), nullable=True),
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
        "idx_sys_tenant_object_storage_tenant_id",
        "sys_tenant_object_storage",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_sys_tenant_object_storage_tenant_id", table_name="sys_tenant_object_storage")
    op.drop_table("sys_tenant_object_storage")
