"""Pack size per part, and stored order suggestions (one run, many lines).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('parts', sa.Column('pack_size', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('order_runs',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
    sa.Column('history_last_day', sa.Date(), nullable=True),
    sa.Column('budget', sa.Integer(), nullable=True),
    sa.Column('suggested_cost', sa.Integer(), nullable=False),
    sa.Column('kept_cost', sa.Integer(), nullable=False),
    sa.Column('kept_lines', sa.Integer(), nullable=False),
    sa.Column('cut_lines', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_order_runs_organization_id'), 'order_runs', ['organization_id'])
    op.create_table('order_suggestions',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('run_id', sa.Uuid(), sa.ForeignKey('order_runs.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('supplier_id', sa.Uuid(), sa.ForeignKey('suppliers.id'), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('rule', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('on_hand', sa.Integer(), nullable=False),
    sa.Column('on_order', sa.Integer(), nullable=False),
    sa.Column('pack_size', sa.Integer(), nullable=False),
    sa.Column('delivery_days', sa.Integer(), nullable=False),
    sa.Column('days_covered', sa.Integer(), nullable=False),
    sa.Column('expected', sa.Float(), nullable=False),
    sa.Column('cushion', sa.Float(), nullable=False),
    sa.Column('need', sa.Integer(), nullable=False),
    sa.Column('sold_last_90_days', sa.Integer(), nullable=False),
    sa.Column('unit_cost', sa.Integer(), nullable=True),
    sa.Column('line_cost', sa.Integer(), nullable=False),
    sa.Column('missed_sales_prevented', sa.Float(), nullable=False),
    sa.Column('value_per_dirham', sa.Float(), nullable=True),
    sa.Column('reason', sa.String(length=400), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_order_suggestions_organization_id'), 'order_suggestions', ['organization_id'])
    op.create_index(op.f('ix_order_suggestions_run_id'), 'order_suggestions', ['run_id'])


def downgrade() -> None:
    op.drop_table('order_suggestions')
    op.drop_table('order_runs')
    op.drop_column('parts', 'pack_size')
