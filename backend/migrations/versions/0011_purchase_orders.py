"""Purchase orders, approving/rejecting suggestions, and how careful orders should be.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('order_service_target', sa.Float(), nullable=False, server_default='0.9'))

    op.create_table('purchase_orders',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('supplier_id', sa.Uuid(), sa.ForeignKey('suppliers.id'), nullable=False),
    sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
    sa.Column('order_number', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_purchase_orders_organization_id'), 'purchase_orders', ['organization_id'])
    op.create_unique_constraint('purchase_orders_number_unique', 'purchase_orders', ['organization_id', 'order_number'])

    op.create_table('purchase_order_lines',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('purchase_order_id', sa.Uuid(), sa.ForeignKey('purchase_orders.id'), nullable=False),
    sa.Column('part_id', sa.Uuid(), sa.ForeignKey('parts.id'), nullable=False),
    sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id'), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('received_quantity', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('unit_cost', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f('ix_purchase_order_lines_organization_id'), 'purchase_order_lines', ['organization_id'])
    op.create_index(op.f('ix_purchase_order_lines_purchase_order_id'), 'purchase_order_lines', ['purchase_order_id'])

    op.add_column('order_suggestions', sa.Column('approved_quantity', sa.Integer(), nullable=True))
    op.add_column(
        'order_suggestions',
        sa.Column('purchase_order_line_id', sa.Uuid(), sa.ForeignKey('purchase_order_lines.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('order_suggestions', 'purchase_order_line_id')
    op.drop_column('order_suggestions', 'approved_quantity')
    op.drop_table('purchase_order_lines')
    op.drop_table('purchase_orders')
    op.drop_column('organizations', 'order_service_target')
