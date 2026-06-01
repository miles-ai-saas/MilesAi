"""biz_suppliers

Revision ID: c9d5f3a2b014
Revises: b8c4e2f1a903
Create Date: 2026-06-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9d5f3a2b014"
down_revision: Union[str, None] = "b8c4e2f1a903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "biz_suppliers",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("contact_name", sa.String(length=128), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.String(length=128), nullable=True),
        sa.Column("bank_account", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_biz_suppliers_tenant", "biz_suppliers", ["tenant_id"], unique=False)
    op.create_index("idx_biz_suppliers_category", "biz_suppliers", ["tenant_id", "category"], unique=False)
    op.create_index("idx_biz_suppliers_status", "biz_suppliers", ["tenant_id", "status"], unique=False)

    op.create_table(
        "biz_supplier_contacts",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_biz_supplier_contacts_supplier", "biz_supplier_contacts", ["tenant_id", "supplier_id"], unique=False)

    op.create_table(
        "biz_project_suppliers",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("work_package_id", sa.UUID(), nullable=True),
        sa.Column("role_description", sa.String(length=256), nullable=True),
        sa.Column("contracted_amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("project_id", "supplier_id"),
    )
    op.create_index("idx_biz_ps_tenant", "biz_project_suppliers", ["tenant_id"], unique=False)
    op.create_index("idx_biz_ps_project", "biz_project_suppliers", ["tenant_id", "project_id"], unique=False)
    op.create_index("idx_biz_ps_supplier", "biz_project_suppliers", ["tenant_id", "supplier_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_biz_ps_supplier", table_name="biz_project_suppliers")
    op.drop_index("idx_biz_ps_project", table_name="biz_project_suppliers")
    op.drop_index("idx_biz_ps_tenant", table_name="biz_project_suppliers")
    op.drop_table("biz_project_suppliers")
    op.drop_index("idx_biz_supplier_contacts_supplier", table_name="biz_supplier_contacts")
    op.drop_table("biz_supplier_contacts")
    op.drop_index("idx_biz_suppliers_status", table_name="biz_suppliers")
    op.drop_index("idx_biz_suppliers_category", table_name="biz_suppliers")
    op.drop_index("idx_biz_suppliers_tenant", table_name="biz_suppliers")
    op.drop_table("biz_suppliers")
