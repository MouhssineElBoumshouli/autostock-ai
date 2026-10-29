from typing import Literal

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Language = Literal["en", "fr", "ar"]


class Organization(Base):
    """One shop (or group of branches). Every other table points to one."""

    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("language IN ('en', 'fr', 'ar')", name="organizations_language_valid"),)

    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
    # The language people see unless they choose their own (User.language).
    language: Mapped[str] = mapped_column(String(2), default="fr", server_default="fr")
    # A made-up shop for demos and for measuring forecasts. Real shops are never demo shops.
    is_demo: Mapped[bool] = mapped_column(default=False)
    # How careful "what to order" suggestions should be: 0.8 (save money), 0.9 (balanced), 0.95 (never run out).
    order_service_target: Mapped[float] = mapped_column(default=0.9)
    # The owner let the cloud writer (Groq) write "Ask your shop" answers. Off: the app writes them.
    cloud_writer_on: Mapped[bool] = mapped_column(default=False, server_default="false")
    # The owner or a manager hid the "Start here" checklist on Today (a new shop finished it, or knows its own way).
    start_here_hidden: Mapped[bool] = mapped_column(default=False, server_default="false")
