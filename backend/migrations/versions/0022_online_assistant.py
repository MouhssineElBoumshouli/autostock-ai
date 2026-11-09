"""Ask becomes a real assistant: the owner's switch for the cloud writer becomes the switch for the online
assistant (Groq thinks, the app's read-only tools give the facts). On by default (owner-approved change),
so it works as soon as GROQ_API_KEY is set; the owner can still turn it off in Settings.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("organizations", "cloud_writer_on", new_column_name="online_assistant_on",
                    server_default=sa.true())
    op.execute("UPDATE organizations SET online_assistant_on = true")


def downgrade() -> None:
    op.alter_column("organizations", "online_assistant_on", new_column_name="cloud_writer_on",
                    server_default=sa.false())
    op.execute("UPDATE organizations SET cloud_writer_on = false")
