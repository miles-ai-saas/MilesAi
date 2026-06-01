"""biz_opportunities_contracts

Revision ID: 697bc17a1854
Revises: ae613709947f
Create Date: 2026-06-01 11:24:41.205393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '697bc17a1854'
down_revision: Union[str, None] = 'ae613709947f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('biz_contracts',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('contract_no', sa.String(length=64), nullable=True),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('signed_date', sa.Date(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('total_amount', sa.Float(), nullable=True),
    sa.Column('payment_terms', sa.String(length=256), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('attachment_id', sa.UUID(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_ctr_client', 'biz_contracts', ['tenant_id', 'client_id'], unique=False)
    op.create_index('idx_biz_ctr_project', 'biz_contracts', ['tenant_id', 'project_id'], unique=False)
    op.create_index('idx_biz_ctr_status', 'biz_contracts', ['tenant_id', 'status'], unique=False)
    op.create_index('idx_biz_ctr_tenant', 'biz_contracts', ['tenant_id'], unique=False)
    op.create_table('biz_opportunities',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=True),
    sa.Column('stage', sa.String(length=32), nullable=False),
    sa.Column('expected_value', sa.Float(), nullable=True),
    sa.Column('probability', sa.Integer(), nullable=True),
    sa.Column('expected_close_date', sa.Date(), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('converted_to_project_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_opp_client', 'biz_opportunities', ['tenant_id', 'client_id'], unique=False)
    op.create_index('idx_biz_opp_owner', 'biz_opportunities', ['tenant_id', 'owner_id'], unique=False)
    op.create_index('idx_biz_opp_stage', 'biz_opportunities', ['tenant_id', 'stage'], unique=False)
    op.create_index('idx_biz_opp_tenant', 'biz_opportunities', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_biz_opp_tenant', table_name='biz_opportunities')
    op.drop_index('idx_biz_opp_stage', table_name='biz_opportunities')
    op.drop_index('idx_biz_opp_owner', table_name='biz_opportunities')
    op.drop_index('idx_biz_opp_client', table_name='biz_opportunities')
    op.drop_table('biz_opportunities')
    op.drop_index('idx_biz_ctr_tenant', table_name='biz_contracts')
    op.drop_index('idx_biz_ctr_status', table_name='biz_contracts')
    op.drop_index('idx_biz_ctr_project', table_name='biz_contracts')
    op.drop_index('idx_biz_ctr_client', table_name='biz_contracts')
    op.drop_table('biz_contracts')
