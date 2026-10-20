import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Alert(Base):
    """Something unusual a person should look at: a sales spike or drop, or stock that doesn't
    match sales. Raised by the daily check; owners and managers mark it "Looked at it" or
    "Not a problem". Alerts never change data by themselves."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_org_raised", "organization_id", "raised_on"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    kind: Mapped[str] = mapped_column(String(30))  # sales_spike, sales_drop, sold_at_zero, stock_frozen, negative_stock
    sentence: Mapped[str] = mapped_column(String(300))
    numbers: Mapped[dict] = mapped_column(JSONB)  # the real numbers in the sentence
    money_at_stake: Mapped[int]  # centimes
    started_on: Mapped[date]
    raised_on: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, looked_at, not_a_problem
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
