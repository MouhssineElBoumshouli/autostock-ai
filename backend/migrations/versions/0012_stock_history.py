"""Stock on the shelf day by day, and the problems planted in the demo shop.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('stock_history',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_stock_history_org_part_day', 'stock_history', ['organization_id', 'part_id', 'branch_id', 'day'])

    op.create_table('demo_planted_problems',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('first_day', sa.Date(), nullable=False),
    sa.Column('last_day', sa.Date(), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_demo_planted_problems_organization_id'), 'demo_planted_problems', ['organization_id'])


def downgrade() -> None:
    op.drop_table('demo_planted_problems')
    op.drop_table('stock_history')
