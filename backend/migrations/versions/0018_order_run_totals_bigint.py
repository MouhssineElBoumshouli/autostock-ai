"""Order run totals as big integers: a big shop's first suggestions came to 269.9 million MAD,
more than a plain integer of centimes holds (21.5 million MAD), and "Make suggestions" failed.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

COLUMNS = ("budget", "suggested_cost", "kept_cost")


def upgrade() -> None:
    for column in COLUMNS:
        op.alter_column("order_runs", column, type_=sa.BigInteger())


def downgrade() -> None:
    for column in COLUMNS:
        op.alter_column("order_runs", column, type_=sa.Integer())
