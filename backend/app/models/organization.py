from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Organization(Base):
    """One shop (or group of branches). Every other table points to one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
    # A made-up shop for demos and for measuring forecasts. Real shops are never demo shops.
    is_demo: Mapped[bool] = mapped_column(default=False)
    # How careful "what to order" suggestions should be: 0.8 (save money), 0.9 (balanced), 0.95 (never run out).
    order_service_target: Mapped[float] = mapped_column(default=0.9)
