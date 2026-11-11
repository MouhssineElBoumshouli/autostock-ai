"""Delivery times without typing: each supplier remembers where its delivery time came from (the
shop's file, its own deliveries, or the owner), each received order how many days it took, and each
order suggestion which delivery time it used.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-07
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("delivery_source", sa.String(10), nullable=True))
    op.add_column("suppliers", sa.Column("delivery_learned_from", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("purchase_orders", sa.Column("days_taken", sa.Integer(), nullable=True))
    op.add_column("order_suggestions", sa.Column("delivery_source", sa.String(10), nullable=True))
    op.add_column("order_suggestions", sa.Column("delivery_learned_from", sa.Integer(), nullable=False, server_default="0"))

    # A delivery time already there was typed by someone (or came with the demo): it stays theirs.
    op.execute("UPDATE suppliers SET delivery_source = 'owner' WHERE delivery_days IS NOT NULL")
    # Orders already received: days from sent to received, on the shop's calendar, at least 1.
    op.execute(sa.text(
        """UPDATE purchase_orders
           SET days_taken = greatest(1, CAST(received_at AT TIME ZONE :zone AS date) - CAST(sent_at AT TIME ZONE :zone AS date))
           WHERE received_at IS NOT NULL AND sent_at IS NOT NULL"""
    ).bindparams(zone=os.environ.get("TZ", "Africa/Casablanca")))


def downgrade() -> None:
    op.drop_column("order_suggestions", "delivery_learned_from")
    op.drop_column("order_suggestions", "delivery_source")
    op.drop_column("purchase_orders", "days_taken")
    op.drop_column("suppliers", "delivery_learned_from")
    op.drop_column("suppliers", "delivery_source")
