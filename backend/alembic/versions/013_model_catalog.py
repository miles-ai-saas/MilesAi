"""模型目录字段 + 租户 BYOK 凭证表

Revision ID: 013
Revises: 012
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _col_exists("agt_model_configs", "vendor"):
        op.add_column(
            "agt_model_configs",
            sa.Column("model_code", sa.String(128), nullable=True),
        )
        op.add_column(
            "agt_model_configs",
            sa.Column("vendor", sa.String(32), server_default="other", nullable=False),
        )
        op.add_column(
            "agt_model_configs",
            sa.Column("model_type", sa.String(32), server_default="llm", nullable=False),
        )
        op.add_column("agt_model_configs", sa.Column("description", sa.Text(), nullable=True))
        op.add_column(
            "agt_model_configs",
            sa.Column("context_window", sa.String(32), nullable=True),
        )
        op.add_column(
            "agt_model_configs",
            sa.Column(
                "capabilities",
                postgresql.JSONB(),
                server_default="[]",
                nullable=False,
            ),
        )
        op.add_column(
            "agt_model_configs",
            sa.Column(
                "publish_status",
                sa.String(16),
                server_default="published",
                nullable=False,
            ),
        )
        op.add_column(
            "agt_model_configs",
            sa.Column("is_featured", sa.Boolean(), server_default="false", nullable=False),
        )
        op.add_column("agt_model_configs", sa.Column("badge", sa.String(16), nullable=True))
        op.add_column(
            "agt_model_configs",
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        )
        op.create_index("idx_agt_model_configs_vendor", "agt_model_configs", ["vendor"])
        op.create_index(
            "idx_agt_model_configs_publish", "agt_model_configs", ["publish_status"]
        )

    if not _table_exists("agt_model_tenant_credentials"):
        op.create_table(
            "agt_model_tenant_credentials",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("model_config_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("api_base", sa.String(512), nullable=True),
            sa.Column("api_key_encrypted", sa.String(512), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "model_config_id", name="un_agt_model_tenant_cred"
            ),
        )
        op.create_index(
            "idx_agt_model_tenant_cred_tenant",
            "agt_model_tenant_credentials",
            ["tenant_id"],
        )


def downgrade() -> None:
    if _table_exists("agt_model_tenant_credentials"):
        op.drop_index("idx_agt_model_tenant_cred_tenant", "agt_model_tenant_credentials")
        op.drop_table("agt_model_tenant_credentials")
    if _col_exists("agt_model_configs", "vendor"):
        op.drop_index("idx_agt_model_configs_publish", "agt_model_configs")
        op.drop_index("idx_agt_model_configs_vendor", "agt_model_configs")
        for col in (
            "sort_order",
            "badge",
            "is_featured",
            "publish_status",
            "capabilities",
            "context_window",
            "description",
            "model_type",
            "vendor",
            "model_code",
        ):
            op.drop_column("agt_model_configs", col)
