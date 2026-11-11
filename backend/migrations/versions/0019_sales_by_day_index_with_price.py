"""The sales-by-day index also carries the price, so the data export reads a day's sales lines
from the index alone. Without it, a 50,000-part shop's export fetched each of its 20 million
lines from the table one by one and took over 10 minutes; with it, under 4.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-02
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_sale_lines_org_day", table_name="sale_lines")
    op.create_index(
        "ix_sale_lines_org_day", "sale_lines", ["organization_id", "sold_on"],
        postgresql_include=["part_id", "branch_id", "quantity", "unit_price"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_lines_org_day", table_name="sale_lines")
    op.create_index(
        "ix_sale_lines_org_day", "sale_lines", ["organization_id", "sold_on"],
        postgresql_include=["part_id", "branch_id", "quantity"],
    )
