"""Ask history (each person's last questions and answers) and the owner's cloud writer switch.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('cloud_writer_on', sa.Boolean(), nullable=False, server_default='false'))
    op.create_table('asked_questions',
    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id'), nullable=False),
    sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('question', sa.String(length=300), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_asked_questions_user', 'asked_questions', ['organization_id', 'user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('asked_questions')
    op.drop_column('organizations', 'cloud_writer_on')
