"""prompt templates, skill packages, agent prompt_template_id

Revision ID: 002
Revises: 001
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "prm_prompt_templates" not in tables:
        op.create_table(
            "prm_prompt_templates",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.String(256), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )
        op.create_index("idx_prm_prompt_templates_tenant_id", "prm_prompt_templates", ["tenant_id"])
        op.create_index(
            "un_prm_prompt_templates_tenant_id_name",
            "prm_prompt_templates",
            ["tenant_id", "name"],
            unique=True,
        )

    if "skl_skill_packages" not in tables:
        op.create_table(
            "skl_skill_packages",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tool_names", JSONB(), nullable=False, server_default="[]"),
            sa.Column("prompt_snippet", sa.Text(), nullable=True),
            sa.Column("config", JSONB(), nullable=False, server_default="{}"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )
        op.create_index("idx_skl_skill_packages_tenant_id", "skl_skill_packages", ["tenant_id"])
        op.create_index(
            "un_skl_skill_packages_tenant_id_name",
            "skl_skill_packages",
            ["tenant_id", "name"],
            unique=True,
        )

    if "agt_agents" in tables:
        cols = {c["name"] for c in insp.get_columns("agt_agents")}
        if "prompt_template_id" not in cols:
            op.add_column("agt_agents", sa.Column("prompt_template_id", UUID(as_uuid=True), nullable=True))
            op.create_index("idx_agt_agents_prompt_template_id", "agt_agents", ["prompt_template_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "agt_agents" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("agt_agents")}
        if "prompt_template_id" in cols:
            op.drop_index("idx_agt_agents_prompt_template_id", table_name="agt_agents")
            op.drop_column("agt_agents", "prompt_template_id")
    if "skl_skill_packages" in insp.get_table_names():
        op.drop_table("skl_skill_packages")
    if "prm_prompt_templates" in insp.get_table_names():
        op.drop_table("prm_prompt_templates")
