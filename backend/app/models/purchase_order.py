import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PurchaseOrder(Base):
    """One order sent to one supplier. Lines come from suggestions a manager approved.
    Receiving (even partial) adds the quantities straight to stock."""

    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("organization_id", "order_number", name="purchase_orders_number_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    order_number: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, sent, received
    sent_at: Mapped[datetime | None]
    received_at: Mapped[datetime | None]  # set once every line is fully received


class PurchaseOrderLine(Base):
    """One part, for one branch, on one purchase order."""

    __tablename__ = "purchase_order_lines"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    quantity: Mapped[int]
    received_quantity: Mapped[int] = mapped_column(default=0)
    unit_cost: Mapped[int | None]  # centimes, snapshot from the part when approved
