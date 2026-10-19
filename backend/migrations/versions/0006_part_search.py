"""Part search: pg_trgm + unaccent, normalized search columns on parts, per-shop synonym list.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18
"""

import uuid
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.search.default_synonyms import DEFAULT_SYNONYMS

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

# Lowercase, no accents, Arabic letter variants made the same (أ إ آ ٱ -> ا, ى -> ي, ة -> ه,
# ؤ -> و, ئ -> ي), Arabic diacritics and tatweel removed, "ال" dropped from the start of words,
# and punctuation turned into spaces. IMMUTABLE so it can fill generated columns and indexes.
SEARCH_TEXT = r"""
CREATE FUNCTION search_text(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT trim(regexp_replace(
    regexp_replace(
      translate(
        regexp_replace(lower(public.unaccent('public.unaccent'::regdictionary, coalesce(value, ''))),
                       '[ً-ٰٟـ]', '', 'g'),
        'أإآٱىةؤئ', 'اااايهوي'),
      '(^|\s)ال(\S\S)', '\1\2', 'g'),
    '[^a-z0-9ء-ي]+', ' ', 'g'))
$$
"""

# Part numbers compared without spaces, dashes, dots or slashes: "0 986 494 525" = "0986494525".
SEARCH_CODE = r"""
CREATE FUNCTION search_code(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT regexp_replace(lower(coalesce(value, '')), '[^a-z0-9]+', '', 'g')
$$
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(SEARCH_TEXT)
    op.execute(SEARCH_CODE)

    # Starts with a space, so " amort" finds any word starting with "amort" with one LIKE.
    op.add_column('parts', sa.Column(
        'search_words', sa.Text(),
        sa.Computed("' ' || search_text(name || ' ' || coalesce(brand, '') || ' ' || coalesce(category, ''))", persisted=True),
    ))
    op.add_column('parts', sa.Column('sku_key', sa.Text(), sa.Computed('search_code(sku)', persisted=True)))
    op.add_column('parts', sa.Column('oem_key', sa.Text(), sa.Computed('search_code(oem_reference)', persisted=True)))
    for column in ('search_words', 'sku_key', 'oem_key'):
        op.create_index(f'ix_parts_{column}_trgm', 'parts', [column], postgresql_using='gin',
                        postgresql_ops={column: 'gin_trgm_ops'})

    op.create_table('synonym_groups',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('words', postgresql.ARRAY(sa.String(length=100)), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_synonym_groups_organization_id'), 'synonym_groups', ['organization_id'], unique=False)

    # Shops that already exist start with the default list, like new shops do.
    groups = sa.table('synonym_groups', sa.column('id', sa.Uuid()), sa.column('organization_id', sa.Uuid()),
                      sa.column('words', postgresql.ARRAY(sa.String())), sa.column('created_at', sa.DateTime(timezone=True)))
    connection = op.get_bind()
    for (organization_id,) in connection.execute(sa.text('SELECT id FROM organizations')).all():
        op.bulk_insert(groups, [
            {'id': uuid.uuid4(), 'organization_id': organization_id, 'words': words, 'created_at': datetime.now(UTC)}
            for words in DEFAULT_SYNONYMS
        ])


def downgrade() -> None:
    op.drop_index(op.f('ix_synonym_groups_organization_id'), table_name='synonym_groups')
    op.drop_table('synonym_groups')
    for column in ('search_words', 'sku_key', 'oem_key'):
        op.drop_index(f'ix_parts_{column}_trgm', table_name='parts')
        op.drop_column('parts', column)
    op.execute('DROP FUNCTION search_code(text)')
    op.execute('DROP FUNCTION search_text(text)')
