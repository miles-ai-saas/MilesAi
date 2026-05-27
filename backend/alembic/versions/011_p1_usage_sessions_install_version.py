"""P1: 模型用量日志 + 安装版本号

Revision ID: 011
Revises: 010
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agt_model_usage_logs" not in tables:
        op.create_table(
            "agt_model_usage_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("model_config_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("model_name", sa.String(128), nullable=False),
            sa.Column("source", sa.String(32), nullable=False, server_default="chat"),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
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
            "idx_agt_model_usage_logs_tenant_id", "agt_model_usage_logs", ["tenant_id"]
        )
        op.create_index(
            "idx_agt_model_usage_logs_model_id",
            "agt_model_usage_logs",
            ["model_config_id"],
        )
        op.create_index(
            "idx_agt_model_usage_logs_created_at",
            "agt_model_usage_logs",
            ["created_at"],
        )

    if "mkt_installs" in tables:
        cols = {c["name"] for c in inspector.get_columns("mkt_installs")}
        if "installed_version" not in cols:
            op.add_column(
                "mkt_installs",
                sa.Column(
                    "installed_version",
                    sa.String(32),
                    nullable=False,
                    server_default="1.0.0",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "mkt_installs" in tables:
        cols = {c["name"] for c in inspector.get_columns("mkt_installs")}
        if "installed_version" in cols:
            op.drop_column("mkt_installs", "installed_version")

    if "agt_model_usage_logs" in tables:
        op.drop_index("idx_agt_model_usage_logs_created_at", table_name="agt_model_usage_logs")
        op.drop_index("idx_agt_model_usage_logs_model_id", table_name="agt_model_usage_logs")
        op.drop_index("idx_agt_model_usage_logs_tenant_id", table_name="agt_model_usage_logs")
        op.drop_table("agt_model_usage_logs")
