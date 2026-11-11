"""Equivalent parts: a manager's link, or a row from a supplier's cross-reference file, saying
two parts are the same part under another brand. Same-OEM-number equivalents need no table: they
are found live by comparing parts.oem_key, the column search already uses.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('part_equivalents',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('part_a_id', sa.Uuid(), nullable=False),
    sa.Column('part_b_id', sa.Uuid(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("part_a_id < part_b_id", name='part_equivalents_ordered'),
    sa.CheckConstraint("source IN ('manual', 'supplier_file')", name='part_equivalents_source_valid'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['part_a_id'], ['parts.id'], ),
    sa.ForeignKeyConstraint(['part_b_id'], ['parts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'part_a_id', 'part_b_id', name='part_equivalents_pair_unique'),
    )
    op.create_index(op.f('ix_part_equivalents_organization_id'), 'part_equivalents', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_part_equivalents_organization_id'), table_name='part_equivalents')
    op.drop_table('part_equivalents')
