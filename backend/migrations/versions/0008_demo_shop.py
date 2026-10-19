"""Demo shop: organizations.is_demo, stock-out periods, and the true demand a demo shop was made from.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def _per_part_columns() -> list:
    return [
        sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
        sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    ]


def upgrade() -> None:
    op.add_column('organizations', sa.Column('is_demo', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table('stock_outs',
    *_per_part_columns(),
    sa.Column('first_day', sa.Date(), nullable=False),
    sa.Column('last_day', sa.Date(), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('first_day <= last_day', name='stock_outs_days_ordered'),
    )
    op.create_index('ix_stock_outs_org_part', 'stock_outs', ['organization_id', 'part_id', 'branch_id'])
    op.create_table('demo_true_demand',
    *_per_part_columns(),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_demo_true_demand_org_part', 'demo_true_demand', ['organization_id', 'part_id', 'branch_id'])


def downgrade() -> None:
    op.drop_table('demo_true_demand')
    op.drop_table('stock_outs')
    op.drop_column('organizations', 'is_demo')
