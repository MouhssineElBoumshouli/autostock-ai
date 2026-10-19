"""Forecasts: remake them on demand, see how the last run went, and one part's "Expected to sell"."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.forecast.backtest import MIN_WINDOWS
from app.forecast.engine import HORIZONS
from app.forecast.explain import beat_baseline_pct
from app.forecast.run import run_forecasts_in_background
from app.models import Forecast, ForecastRun, Part, SaleLine, User

router = APIRouter(prefix="/api/forecasts")
managers = require_role("owner", "manager")
anyone = require_role()

WEEKS_SHOWN = 12
Method = Literal["four_week_average", "last_week", "exponential_smoothing", "croston", "sba", "tsb", "boosting"]


class RunOut(BaseModel):
    trigger: str
    status: str
    seconds: float
    series_count: int
    history_last_day: date | None
    created_at: datetime


@router.post("/run", status_code=202)
def run_now(background: BackgroundTasks, user: User = Depends(managers), db: Session = Depends(get_session)) -> dict:
    """Starts a new forecast run. It takes up to a minute; the answer comes back at once."""
    record_change(db, user, "forecast.requested", "forecast_run", uuid.uuid4())
    db.commit()
    background.add_task(run_forecasts_in_background, user.organization_id, "manual")
    return {"status": "started"}


@router.get("/runs/latest")
def latest_run(user: User = Depends(anyone), db: Session = Depends(get_session)) -> RunOut | None:
    run = db.scalar(
        select(ForecastRun)
        .where(ForecastRun.organization_id == user.organization_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    return RunOut.model_validate(run, from_attributes=True) if run else None


class WeekPoint(BaseModel):
    week_start: date
    quantity: int


class HorizonForecast(BaseModel):
    enough_history: bool
    quantity: int
    low: int
    high: int
    method: Method | None = None  # for the website to word, in its own language; None = not enough history
    beat_baseline_pct: int | None = None  # pieces-off percent better than a 4-week average, on this part's own past


class PartForecast(BaseModel):
    weeks: list[WeekPoint]  # the last WEEKS_SHOWN weeks actually sold, oldest first
    horizons: dict[int, HorizonForecast]  # keyed by 7, 30, 60


@router.get("/part/{part_id}")
def part_forecast(
    part_id: uuid.UUID,
    branch: uuid.UUID | None = None,
    user: User = Depends(anyone),
    db: Session = Depends(get_session),
) -> PartForecast:
    """Per branch when `branch` is given, otherwise the shop total (every branch added together)."""
    if db.scalar(select(Part.id).where(Part.id == part_id, Part.organization_id == user.organization_id)) is None:
        raise HTTPException(404, "This part is not in your shop.")

    rows_filter = [Forecast.organization_id == user.organization_id, Forecast.part_id == part_id]
    if branch:
        rows_filter.append(Forecast.branch_id == branch)
    by_horizon: dict[int, list[Forecast]] = defaultdict(list)
    for row in db.scalars(select(Forecast).where(*rows_filter)):
        by_horizon[row.horizon_days].append(row)

    return PartForecast(
        weeks=_weekly_history(db, user.organization_id, part_id, branch),
        horizons={horizon: _combine(by_horizon.get(horizon, [])) for horizon in HORIZONS},
    )


def _combine(rows: list[Forecast]) -> HorizonForecast:
    """One part can sell in several branches; the shop total adds their forecasts together and
    speaks for the branch that sells the most of it (its method, and how well that method did)."""
    if not rows:
        return HorizonForecast(enough_history=False, quantity=0, low=0, high=0)
    enough = [row for row in rows if row.backtest_windows >= MIN_WINDOWS]
    quantity, low, high = (round(sum(getattr(row, field) for row in rows)) for field in ("quantity", "low", "high"))
    if not enough:
        return HorizonForecast(enough_history=False, quantity=quantity, low=low, high=high)
    best = max(enough, key=lambda row: row.quantity)
    return HorizonForecast(
        enough_history=True,
        quantity=quantity,
        low=low,
        high=high,
        method=best.method,
        beat_baseline_pct=beat_baseline_pct(best.method, best.method_wape, best.baseline_wape),
    )


def _weekly_history(db: Session, organization_id: uuid.UUID, part_id: uuid.UUID, branch_id: uuid.UUID | None) -> list[WeekPoint]:
    """The last WEEKS_SHOWN weeks of real sales, ending on this part's own last sale day."""
    filters = [SaleLine.organization_id == organization_id, SaleLine.part_id == part_id]
    if branch_id:
        filters.append(SaleLine.branch_id == branch_id)
    last_day = db.scalar(select(func.max(SaleLine.sold_on)).where(*filters))
    if last_day is None:
        return []

    first_day = last_day - timedelta(days=WEEKS_SHOWN * 7 - 1)
    daily = dict(
        db.execute(
            select(SaleLine.sold_on, func.sum(SaleLine.quantity))
            .where(*filters, SaleLine.sold_on >= first_day, SaleLine.sold_on <= last_day)
            .group_by(SaleLine.sold_on)
        ).all()
    )
    return [
        WeekPoint(
            week_start=first_day + timedelta(days=7 * week),
            quantity=sum(daily.get(first_day + timedelta(days=7 * week + day), 0) for day in range(7)),
        )
        for week in range(WEEKS_SHOWN)
    ]
