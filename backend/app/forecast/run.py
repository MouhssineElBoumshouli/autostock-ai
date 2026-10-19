"""Reads one shop's sales from the database, runs the engine and stores the forecasts."""

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from time import perf_counter

import numpy as np
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.forecast.engine import forecast_all
from app.forecast.history import demand_matrix
from app.models import Forecast, ForecastRun, Part, SaleLine, StockOut

log = logging.getLogger(__name__)


@dataclass
class ShopDemand:
    keys: list[tuple[uuid.UUID, uuid.UUID]]  # (part_id, branch_id) for each row of `demand`
    demand: np.ndarray
    first_day: date
    last_day: date


def load_demand(db: Session, organization_id: uuid.UUID) -> ShopDemand | None:
    """Daily demand of every active part in every branch where it ever sold. None without sales.
    The history ends on the last day with a sale in the shop (later days are not imported yet)."""
    sold = db.execute(
        select(SaleLine.part_id, SaleLine.branch_id, SaleLine.sold_on, func.sum(SaleLine.quantity))
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == organization_id, Part.is_active)
        .group_by(SaleLine.part_id, SaleLine.branch_id, SaleLine.sold_on)
    ).all()
    if not sold:
        return None
    first_day = min(row[2] for row in sold)
    last_day = max(row[2] for row in sold)
    keys = sorted({(row[0], row[1]) for row in sold})
    index = {key: i for i, key in enumerate(keys)}
    outs = db.execute(
        select(StockOut.part_id, StockOut.branch_id, StockOut.first_day, StockOut.last_day).where(
            StockOut.organization_id == organization_id
        )
    ).all()
    demand = demand_matrix(
        [(index[(part, branch)], day, int(quantity)) for part, branch, day, quantity in sold],
        [(index[(part, branch)], first, last) for part, branch, first, last in outs if (part, branch) in index],
        len(keys),
        first_day,
        (last_day - first_day).days + 1,
    )
    sells = ~np.isnan(demand).all(axis=1)  # rows with only returns never really sold
    return ShopDemand([key for key, keep in zip(keys, sells) if keep], demand[sells], first_day, last_day)


def run_forecasts(db: Session, organization_id: uuid.UUID, trigger: str) -> ForecastRun:
    """Replaces the shop's forecasts. The caller commits."""
    started = perf_counter()
    shop = load_demand(db, organization_id)
    results = forecast_all(shop.demand, shop.first_day) if shop else []
    db.execute(delete(Forecast).where(Forecast.organization_id == organization_id))
    if results:
        db.execute(
            insert(Forecast),
            [
                {
                    "organization_id": organization_id,
                    "part_id": shop.keys[r.row][0],
                    "branch_id": shop.keys[r.row][1],
                    "horizon_days": r.horizon,
                    "history_last_day": shop.last_day,
                    "demand_type": r.demand_type,
                    "method": r.method,
                    "quantity": round(r.quantity, 2),
                    "low": round(r.low, 2),
                    "high": round(r.high, 2),
                    "method_wape": r.method_wape,
                    "baseline_wape": r.baseline_wape,
                    "method_mase": r.method_mase,
                    "baseline_mase": r.baseline_mase,
                    "backtest_windows": r.windows,
                    "reason": r.reason,
                }
                for r in results
            ],
        )
    run = ForecastRun(
        organization_id=organization_id,
        trigger=trigger,
        status="done",
        seconds=round(perf_counter() - started, 2),
        series_count=len(shop.keys) if shop else 0,
        history_last_day=shop.last_day if shop else None,
    )
    db.add(run)
    return run


def run_forecasts_in_background(organization_id: uuid.UUID, trigger: str) -> None:
    """Runs after the response is sent. One run at a time per shop: a second one waits its turn."""
    with SessionLocal() as db:
        try:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"forecast:{organization_id}"})
            run_forecasts(db, organization_id, trigger)
            db.commit()
        except Exception:
            log.exception("Forecast run failed for %s", organization_id)
            db.rollback()
            db.add(ForecastRun(organization_id=organization_id, trigger=trigger, status="failed", seconds=0, series_count=0))
            db.commit()
