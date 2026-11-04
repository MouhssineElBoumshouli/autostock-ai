"""A file being imported is followed in its own table, so big files are checked and saved in the
background and the progress bar survives a page reload.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_done", sa.Integer(), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("finishing", sa.Boolean(), nullable=False),
        sa.Column("preview", JSONB(), nullable=False),
        sa.Column("mapping", JSONB()),
        sa.Column("summary", JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_jobs_organization_id", "import_jobs", ["organization_id"])


def downgrade() -> None:
    op.drop_table("import_jobs")
