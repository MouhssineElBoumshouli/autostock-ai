import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utc_now


class ImportJob(Base):
    """One file on its way into the shop, from upload to saved. Kept in the database so the work
    goes on in the background and the screen finds it again after a page reload.

    status: uploaded -> checking -> checked -> saving -> saved, or failed from checking or saving.
    """

    __tablename__ = "import_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    file_name: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    rows_done: Mapped[int] = mapped_column(default=0)
    rows_total: Mapped[int] = mapped_column(default=0)
    finishing: Mapped[bool] = mapped_column(default=False)  # every row read, the database is working
    preview: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mapping: Mapped[dict[str, str] | None] = mapped_column(JSONB)  # column index -> field
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    # Moved on by the running job: a job that stops moving was cut off (power, restart).
    updated_at: Mapped[datetime] = mapped_column(default=utc_now)
