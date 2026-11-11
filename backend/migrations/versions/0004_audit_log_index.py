"""Index audit_log by shop and time, so Activity stays fast.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_audit_log_organization_created", "audit_log", ["organization_id", "created_at"])
    # The new index starts with organization_id, so the old one-column index is no longer needed.
    op.drop_index("ix_audit_log_organization_id", table_name="audit_log")


def downgrade() -> None:
    op.create_index("ix_audit_log_organization_id", "audit_log", ["organization_id"])
    op.drop_index("ix_audit_log_organization_created", table_name="audit_log")
