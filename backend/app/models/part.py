import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Part(Base):
    """A part the shop sells. Money is in centimes (12,50 MAD = 1250)."""

    __tablename__ = "parts"
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="parts_sku_unique"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    # Stored in capitals without surrounding spaces, so "bp-001 " and "BP-001" are the same part.
    sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(200))
    oem_reference: Mapped[str | None] = mapped_column(String(200))
    unit_cost: Mapped[int | None]
    sale_price: Mapped[int | None]
    min_stock: Mapped[int] = mapped_column(default=0)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
