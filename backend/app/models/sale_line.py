import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SaleLine(Base):
    """One sold part: the history forecasts will learn from. unit_price in centimes."""

    __tablename__ = "sale_lines"
    __table_args__ = (
        Index("ix_sale_lines_part_date", "organization_id", "part_id", "sold_on"),
        # Carries part, branch, quantity and price: "sales between two days" (Today, What to order,
        # Ask, the data export) is answered from the index alone.
        Index("ix_sale_lines_org_day", "organization_id", "sold_on", postgresql_include=["part_id", "branch_id", "quantity", "unit_price"]),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    sold_on: Mapped[date]
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    quantity: Mapped[int]
    unit_price: Mapped[int | None]
