"""Forecasts per part, branch and horizon, and a record of each forecast run.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('forecasts',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('horizon_days', sa.Integer(), nullable=False),
    sa.Column('history_last_day', sa.Date(), nullable=False),
    sa.Column('demand_type', sa.String(length=20), nullable=False),
    sa.Column('method', sa.String(length=40), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('low', sa.Float(), nullable=False),
    sa.Column('high', sa.Float(), nullable=False),
    sa.Column('method_wape', sa.Float(), nullable=True),
    sa.Column('baseline_wape', sa.Float(), nullable=True),
    sa.Column('method_mase', sa.Float(), nullable=True),
    sa.Column('baseline_mase', sa.Float(), nullable=True),
    sa.Column('backtest_windows', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint('organization_id', 'part_id', 'branch_id', 'horizon_days', name='forecasts_part_branch_horizon_unique'),
    )
    op.create_index(op.f('ix_forecasts_organization_id'), 'forecasts', ['organization_id'])
    op.create_table('forecast_runs',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('seconds', sa.Float(), nullable=False),
    sa.Column('series_count', sa.Integer(), nullable=False),
    sa.Column('history_last_day', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_forecast_runs_organization_id'), 'forecast_runs', ['organization_id'])


def downgrade() -> None:
    op.drop_table('forecast_runs')
    op.drop_table('forecasts')
