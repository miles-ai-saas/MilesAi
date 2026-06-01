"""biz_tables

Revision ID: ae613709947f
Revises: 006
Create Date: 2026-06-01 11:20:58.176375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'ae613709947f'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('biz_client_contacts',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('email', sa.String(length=256), nullable=True),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_client_contacts_client', 'biz_client_contacts', ['tenant_id', 'client_id'], unique=False)
    op.create_table('biz_clients',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('short_name', sa.String(length=64), nullable=True),
    sa.Column('industry', sa.String(length=64), nullable=True),
    sa.Column('confidentiality_level', sa.String(length=32), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_clients_tenant', 'biz_clients', ['tenant_id'], unique=False)
    op.create_table('biz_deliverables',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('work_package_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('attachment_id', sa.UUID(), nullable=True),
    sa.Column('media_asset_id', sa.UUID(), nullable=True),
    sa.Column('kb_document_id', sa.UUID(), nullable=True),
    sa.Column('version', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('submitted_at', sa.String(length=32), nullable=True),
    sa.Column('accepted_at', sa.String(length=32), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_deliv_project', 'biz_deliverables', ['tenant_id', 'project_id'], unique=False)
    op.create_index('idx_biz_deliv_tenant', 'biz_deliverables', ['tenant_id'], unique=False)
    op.create_table('biz_project_members',
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role_in_project', sa.String(length=64), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.PrimaryKeyConstraint('project_id', 'user_id')
    )
    op.create_index('idx_biz_pm_project', 'biz_project_members', ['tenant_id', 'project_id'], unique=False)
    op.create_index('idx_biz_pm_tenant', 'biz_project_members', ['tenant_id'], unique=False)
    op.create_table('biz_projects',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('total_budget', sa.Float(), nullable=True),
    sa.Column('opportunity_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_projects_client', 'biz_projects', ['tenant_id', 'client_id'], unique=False)
    op.create_index('idx_biz_projects_owner', 'biz_projects', ['tenant_id', 'owner_id'], unique=False)
    op.create_index('idx_biz_projects_status', 'biz_projects', ['tenant_id', 'status'], unique=False)
    op.create_index('idx_biz_projects_tenant', 'biz_projects', ['tenant_id'], unique=False)
    op.create_table('biz_service_line_templates',
    sa.Column('tenant_id', sa.UUID(), nullable=True),
    sa.Column('service_line', sa.String(length=64), nullable=False),
    sa.Column('stages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_slt_service_line', 'biz_service_line_templates', ['service_line'], unique=False)
    op.create_table('biz_work_packages',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('service_line', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('stage', sa.String(length=64), nullable=True),
    sa.Column('stage_index', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('budget', sa.Float(), nullable=True),
    sa.Column('actual_cost', sa.Float(), nullable=True),
    sa.Column('planned_start', sa.Date(), nullable=True),
    sa.Column('planned_end', sa.Date(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_wp_project', 'biz_work_packages', ['tenant_id', 'project_id'], unique=False)
    op.create_index('idx_biz_wp_service_line', 'biz_work_packages', ['tenant_id', 'service_line'], unique=False)
    op.create_index('idx_biz_wp_status', 'biz_work_packages', ['tenant_id', 'status'], unique=False)
    op.create_index('idx_biz_wp_tenant', 'biz_work_packages', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_biz_wp_tenant', table_name='biz_work_packages')
    op.drop_index('idx_biz_wp_status', table_name='biz_work_packages')
    op.drop_index('idx_biz_wp_service_line', table_name='biz_work_packages')
    op.drop_index('idx_biz_wp_project', table_name='biz_work_packages')
    op.drop_table('biz_work_packages')
    op.drop_index('idx_biz_slt_service_line', table_name='biz_service_line_templates')
    op.drop_table('biz_service_line_templates')
    op.drop_index('idx_biz_projects_tenant', table_name='biz_projects')
    op.drop_index('idx_biz_projects_status', table_name='biz_projects')
    op.drop_index('idx_biz_projects_owner', table_name='biz_projects')
    op.drop_index('idx_biz_projects_client', table_name='biz_projects')
    op.drop_table('biz_projects')
    op.drop_index('idx_biz_pm_tenant', table_name='biz_project_members')
    op.drop_index('idx_biz_pm_project', table_name='biz_project_members')
    op.drop_table('biz_project_members')
    op.drop_index('idx_biz_deliv_tenant', table_name='biz_deliverables')
    op.drop_index('idx_biz_deliv_project', table_name='biz_deliverables')
    op.drop_table('biz_deliverables')
    op.drop_index('idx_biz_clients_tenant', table_name='biz_clients')
    op.drop_table('biz_clients')
    op.drop_index('idx_biz_client_contacts_client', table_name='biz_client_contacts')
    op.drop_table('biz_client_contacts')
