from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Organization(Base):
    """One shop (or group of branches). Every other table points to one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
