import uuid
from datetime import date

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Forecast(Base):
    """Expected demand for one part in one branch over the next 7, 30 or 60 days, with the method
    used and how it scored against the 4-week-average baseline on this part's own past.
    Replaced on every forecast run; created_at is the run date."""

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("organization_id", "part_id", "branch_id", "horizon_days", name="forecasts_part_branch_horizon_unique"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    horizon_days: Mapped[int]
    history_last_day: Mapped[date]  # forecasts cover the days after this one
    demand_type: Mapped[str] = mapped_column(String(20))  # smooth, erratic, slow, lumpy, no_sales
    method: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[float]  # pieces over the whole horizon
    low: Mapped[float]
    high: Mapped[float]
    method_wape: Mapped[float | None]
    baseline_wape: Mapped[float | None]
    method_mase: Mapped[float | None]
    baseline_mase: Mapped[float | None]
    backtest_windows: Mapped[int]
    reason: Mapped[str] = mapped_column(String(300))


class ForecastRun(Base):
    """One time the forecasts were remade: after a sales import, or when a manager asked."""

    __tablename__ = "forecast_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(20))  # sales_import, manual
    status: Mapped[str] = mapped_column(String(20))  # done, failed
    seconds: Mapped[float]
    series_count: Mapped[int]  # parts x branches forecast
    history_last_day: Mapped[date | None]
