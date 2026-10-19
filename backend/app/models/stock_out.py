import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockOut(Base):
    """Days a part had none on the shelf in one branch (first and last day included).

    Zero sales on those days does not mean nobody wanted the part, so forecasts treat them as unknown.
    """

    __tablename__ = "stock_outs"
    __table_args__ = (Index("ix_stock_outs_org_part", "organization_id", "part_id", "branch_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    first_day: Mapped[date]
    last_day: Mapped[date]
