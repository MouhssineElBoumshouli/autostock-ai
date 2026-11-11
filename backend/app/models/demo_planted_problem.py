import uuid
from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DemoPlantedProblem(Base):
    """Demo shops only: a problem we put in the made-up data on purpose, with its true dates, so we
    can measure how many the alerts catch and how fast. Never in a real shop."""

    __tablename__ = "demo_planted_problems"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    kind: Mapped[str] = mapped_column(String(30))  # sales_spike, sales_drop, stock_frozen, sold_at_zero, negative_stock
    first_day: Mapped[date]
    last_day: Mapped[date]  # the last day of the history when it never stopped
    details: Mapped[dict] = mapped_column(JSONB)
