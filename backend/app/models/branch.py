import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Branch(Base):
    """A place where stock is kept. Every shop starts with one, named after the shop."""

    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="branches_name_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
