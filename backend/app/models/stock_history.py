import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockHistory(Base):
    """How many of one part were on the shelf in one branch at the end of a day. Saved only on days
    the number changed: the quantity on any day is the newest row on or before it. Days before the
    first row are unknown. Alerts read it to spot stock that doesn't match sales."""

    __tablename__ = "stock_history"
    __table_args__ = (Index("ix_stock_history_org_part_day", "organization_id", "part_id", "branch_id", "day"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    day: Mapped[date]
    quantity: Mapped[int]
