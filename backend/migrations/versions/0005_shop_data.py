"""Shop data: branches, suppliers, parts, stock levels, sales lines, remembered import matching.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('branches',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='branches_name_unique')
    )
    op.create_index(op.f('ix_branches_organization_id'), 'branches', ['organization_id'], unique=False)
    op.create_table('import_mappings',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'kind', name='import_mappings_kind_unique')
    )
    op.create_table('suppliers',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('delivery_days', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='suppliers_name_unique')
    )
    op.create_index(op.f('ix_suppliers_organization_id'), 'suppliers', ['organization_id'], unique=False)
    op.create_table('parts',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('sku', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=300), nullable=False),
    sa.Column('brand', sa.String(length=200), nullable=True),
    sa.Column('category', sa.String(length=200), nullable=True),
    sa.Column('oem_reference', sa.String(length=200), nullable=True),
    sa.Column('unit_cost', sa.Integer(), nullable=True),
    sa.Column('sale_price', sa.Integer(), nullable=True),
    sa.Column('min_stock', sa.Integer(), nullable=False),
    sa.Column('supplier_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'sku', name='parts_sku_unique')
    )
    op.create_index(op.f('ix_parts_organization_id'), 'parts', ['organization_id'], unique=False)
    op.create_table('sale_lines',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('sold_on', sa.Date(), nullable=False),
    sa.Column('part_id', sa.Uuid(), nullable=False),
    sa.Column('branch_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sale_lines_part_date', 'sale_lines', ['organization_id', 'part_id', 'sold_on'], unique=False)
    op.create_table('stock_levels',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('part_id', sa.Uuid(), nullable=False),
    sa.Column('branch_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('part_id', 'branch_id', name='stock_levels_part_branch_unique')
    )
    op.create_index(op.f('ix_stock_levels_organization_id'), 'stock_levels', ['organization_id'], unique=False)

    # Shops created before this step get their first branch, named after the shop.
    op.execute(
        "INSERT INTO branches (id, organization_id, name, created_at) "
        "SELECT gen_random_uuid(), id, name, now() FROM organizations"
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_levels_organization_id'), table_name='stock_levels')
    op.drop_table('stock_levels')
    op.drop_index('ix_sale_lines_part_date', table_name='sale_lines')
    op.drop_table('sale_lines')
    op.drop_index(op.f('ix_parts_organization_id'), table_name='parts')
    op.drop_table('parts')
    op.drop_index(op.f('ix_suppliers_organization_id'), table_name='suppliers')
    op.drop_table('suppliers')
    op.drop_table('import_mappings')
    op.drop_index(op.f('ix_branches_organization_id'), table_name='branches')
    op.drop_table('branches')
