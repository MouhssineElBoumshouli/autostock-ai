import uuid
from datetime import date

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OrderRun(Base):
    """One time AutoStock worked out what to order. Kept, so every past suggestion can be looked at.
    Nothing is ordered automatically: a person approves lines (Step 5b)."""

    __tablename__ = "order_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    history_last_day: Mapped[date | None]  # the forecasts used were made from sales up to this day
    # Totals in centimes can pass 21.5 million MAD (the most a plain integer holds) in a big shop.
    budget: Mapped[int | None] = mapped_column(BigInteger)  # centimes; None = no limit
    suggested_cost: Mapped[int] = mapped_column(BigInteger)  # every line with something to order, before the budget
    kept_cost: Mapped[int] = mapped_column(BigInteger)
    kept_lines: Mapped[int]
    cut_lines: Mapped[int]


class OrderSuggestion(Base):
    """One part for one branch in one run, with the numbers its quantity came from."""

    __tablename__ = "order_suggestions"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_runs.id"), index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    # suggested, cut_by_budget (still pending a decision), approved, rejected
    status: Mapped[str] = mapped_column(String(20))
    rule: Mapped[str] = mapped_column(String(20))  # forecast, slow_out_of_stock
    quantity: Mapped[int]
    on_hand: Mapped[int]
    on_order: Mapped[int]
    pack_size: Mapped[int]
    delivery_days: Mapped[int]
    days_covered: Mapped[int]
    expected: Mapped[float]  # pieces expected to sell over days_covered
    cushion: Mapped[float]
    need: Mapped[int]
    sold_last_90_days: Mapped[int]
    unit_cost: Mapped[int | None]
    line_cost: Mapped[int]  # centimes
    missed_sales_prevented: Mapped[float]  # pieces
    value_per_dirham: Mapped[float | None]  # lost profit prevented per dirham spent; None = free line
    reason: Mapped[str] = mapped_column(String(400))
    # Set once a manager decides. approved_quantity may differ from `quantity` (the manager can change it).
    approved_quantity: Mapped[int | None]
    # The purchase order line this became, once approved. Locked (no more edits) once that order is sent.
    purchase_order_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_order_lines.id"))
