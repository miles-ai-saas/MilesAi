"""biz_payments

Revision ID: a54ef067f04a
Revises: 697bc17a1854
Create Date: 2026-06-01 11:35:27.583870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a54ef067f04a'
down_revision: Union[str, None] = '697bc17a1854'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('biz_payments',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('direction', sa.String(length=16), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('planned_date', sa.Date(), nullable=True),
    sa.Column('paid_date', sa.Date(), nullable=True),
    sa.Column('method', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_biz_pay_contract', 'biz_payments', ['tenant_id', 'contract_id'], unique=False)
    op.create_index('idx_biz_pay_project', 'biz_payments', ['tenant_id', 'project_id'], unique=False)
    op.create_index('idx_biz_pay_status', 'biz_payments', ['tenant_id', 'status'], unique=False)
    op.create_index('idx_biz_pay_tenant', 'biz_payments', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_biz_pay_tenant', table_name='biz_payments')
    op.drop_index('idx_biz_pay_status', table_name='biz_payments')
    op.drop_index('idx_biz_pay_project', table_name='biz_payments')
    op.drop_index('idx_biz_pay_contract', table_name='biz_payments')
    op.drop_table('biz_payments')
