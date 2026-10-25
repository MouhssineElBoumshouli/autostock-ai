"""Languages: each shop has a default language, each person can choose their own.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('language', sa.String(2), nullable=False, server_default='fr'))
    op.add_column('users', sa.Column('language', sa.String(2), nullable=True))
    op.create_check_constraint('organizations_language_valid', 'organizations', "language IN ('en', 'fr', 'ar')")
    op.create_check_constraint('users_language_valid', 'users', "language IS NULL OR language IN ('en', 'fr', 'ar')")


def downgrade() -> None:
    op.drop_constraint('users_language_valid', 'users')
    op.drop_constraint('organizations_language_valid', 'organizations')
    op.drop_column('users', 'language')
    op.drop_column('organizations', 'language')
