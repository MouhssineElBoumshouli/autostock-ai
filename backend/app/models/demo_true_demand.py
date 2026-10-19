import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DemoTrueDemand(Base):
    """Demo shops only: how many customers really wanted on a day, including days the part was out
    of stock and the days after the sales history ends. Lets us check forecasts against the truth.
    Days not listed had zero demand."""

    __tablename__ = "demo_true_demand"
    __table_args__ = (Index("ix_demo_true_demand_org_part", "organization_id", "part_id", "branch_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    day: Mapped[date]
    quantity: Mapped[int]
