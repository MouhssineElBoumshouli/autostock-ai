"""Index sales lines by shop and day, so "sales between two days" (Today, What to order, Ask)
reads only those days instead of every sales line of the shop. The index also carries the part,
branch and quantity, so those questions are answered from the index alone: a shop whose history
was imported part by part has each day's lines spread over the whole table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-01
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_sale_lines_org_day", "sale_lines", ["organization_id", "sold_on"],
        postgresql_include=["part_id", "branch_id", "quantity"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_lines_org_day", table_name="sale_lines")
