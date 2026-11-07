import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="suppliers_name_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(320))
    # How many days an order takes to arrive, for "what to order". None: not known yet (7 is used).
    delivery_days: Mapped[int | None]
    # Where it came from: "file" (the parts import), "learned" (its received orders), "owner" (typed).
    # See app/ordering/delivery_time.py.
    delivery_source: Mapped[str | None] = mapped_column(String(10))
    delivery_learned_from: Mapped[int] = mapped_column(default=0)  # deliveries behind a "learned" value
