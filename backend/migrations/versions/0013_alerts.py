"""Alerts: unusual sales and stock that doesn't match sales.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('alerts',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('sentence', sa.String(length=300), nullable=False),
    sa.Column('numbers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('money_at_stake', sa.Integer(), nullable=False),
    sa.Column('started_on', sa.Date(), nullable=False),
    sa.Column('raised_on', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_alerts_org_raised', 'alerts', ['organization_id', 'raised_on'])


def downgrade() -> None:
    op.drop_table('alerts')
