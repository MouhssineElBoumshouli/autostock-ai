"""Reads one shop's sales from the database, runs the engine and stores the forecasts."""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
from sqlalchemy import delete, insert, select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.forecast.engine import forecast_all
from app.forecast.history import demand_matrix, first_and_last_day, read_daily_sales, sales_table
from app.models import Forecast, ForecastRun, Organization, StockOut
from app.ordering.run import last_budget, make_order_run
from app.shop_day import shop_today

log = logging.getLogger(__name__)
APP_FOLDER = Path(__file__).resolve().parents[2]  # where `python -m app...` works
LOWER_PRIORITY = 10  # pages, at normal priority, get the processor first while a run works
SAVE_AT_A_TIME = 10_000
CHECK_EVERY_SECONDS = 3600


@dataclass
class ShopDemand:
    keys: list[tuple[uuid.UUID, uuid.UUID]]  # (part_id, branch_id) for each row of `demand`
    demand: np.ndarray | None
    first_day: date
    last_day: date

    def hand_over_demand(self) -> np.ndarray:
        """The demand table, let go of here, so whoever takes it can free it when done."""
        demand, self.demand = self.demand, None
        return demand


def load_demand(db: Session, organization_id: uuid.UUID) -> ShopDemand | None:
    """Daily demand of every active part in every branch where it ever sold. None without sales.
    The history ends on the last day with a sale in the shop (later days are not imported yet)."""
    sales = read_daily_sales(db, organization_id)
    if not sales:
        return None
    first_day, last_day = first_and_last_day(sales)
    keys = sorted(sales)
    index = {key: i for i, key in enumerate(keys)}
    outs = db.execute(
        select(StockOut.part_id, StockOut.branch_id, StockOut.first_day, StockOut.last_day).where(
            StockOut.organization_id == organization_id
        )
    ).all()
    demand = demand_matrix(
        sales_table(sales, keys, first_day, (last_day - first_day).days + 1),
        [(index[(part, branch)], first, last) for part, branch, first, last in outs if (part, branch) in index],
        first_day,
    )
    sells = ~np.isnan(demand).all(axis=1)  # rows with only returns never really sold
    return ShopDemand([key for key, keep in zip(keys, sells) if keep], demand[sells], first_day, last_day)


def run_forecasts(db: Session, organization_id: uuid.UUID, trigger: str) -> ForecastRun:
    """Replaces the shop's forecasts. The caller commits."""
    started = perf_counter()
    shop = load_demand(db, organization_id)
    results = forecast_all(shop.hand_over_demand(), shop.first_day) if shop else []
    db.execute(delete(Forecast).where(Forecast.organization_id == organization_id))
    for start in range(0, len(results), SAVE_AT_A_TIME):  # a big shop has hundreds of thousands
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
                for r in results[start : start + SAVE_AT_A_TIME]
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


def run_forecasts_apart(organization_id: uuid.UUID, trigger: str) -> None:
    """What the website starts (a click, a sales import): the run in its own process at a lower
    priority, so pages stay fast while it works and all its memory is given back when it ends.
    Waits for it to finish."""
    finished = subprocess.run([sys.executable, "-m", "app.forecast.run", str(organization_id), trigger], cwd=APP_FOLDER)
    if finished.returncode != 0:  # stopped from outside (out of memory, ...): it could not record that itself
        log.error("Forecast run for %s stopped with code %s", organization_id, finished.returncode)
        _record_failed_run(organization_id, trigger)


def run_forecasts_in_background(organization_id: uuid.UUID, trigger: str) -> None:
    """One run at a time per shop: a second one waits its turn. Order suggestions are then remade
    too, so nobody has to click for them after a forecast run (nightly, an import, or a click)."""
    with SessionLocal() as db:
        try:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"forecast:{organization_id}"})
            run_forecasts(db, organization_id, trigger)
            make_order_run(db, organization_id, last_budget(db, organization_id))
            db.commit()
        except Exception:
            log.exception("Forecast run failed for %s", organization_id)
            db.rollback()
            _record_failed_run(organization_id, trigger)


def _record_failed_run(organization_id: uuid.UUID, trigger: str) -> None:
    with SessionLocal() as db:
        db.add(ForecastRun(organization_id=organization_id, trigger=trigger, status="failed", seconds=0, series_count=0))
        db.commit()


async def keep_running_forecasts() -> None:
    """Runs while the server is up: once a day per real shop, checked hourly so a restart never
    skips a day. Whether a shop already ran today is checked against the database (any trigger:
    an import or a click count too), not kept in memory -- a restart must never start a second,
    long run on a big shop that already ran today. The demo shop's forecasts come from its own
    replay script, not this loop."""
    while True:
        today = shop_today()
        try:
            with SessionLocal() as db:
                shops = db.scalars(select(Organization.id).where(~Organization.is_demo)).all()
            for shop_id in shops:
                if not await asyncio.to_thread(ran_today, shop_id, today):
                    await asyncio.to_thread(run_forecasts_apart, shop_id, "nightly")
        except Exception:
            log.exception("Nightly forecasts failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def ran_today(organization_id: uuid.UUID, today: date) -> bool:
    """Whether a forecast run already finished today, from any trigger."""
    with SessionLocal() as db:
        latest = db.scalar(
            select(ForecastRun.created_at)
            .where(ForecastRun.organization_id == organization_id, ForecastRun.status == "done")
            .order_by(ForecastRun.created_at.desc())
            .limit(1)
        )
    return latest is not None and shop_today(latest) == today


if __name__ == "__main__":  # started by run_forecasts_apart
    os.nice(LOWER_PRIORITY)
    run_forecasts_in_background(uuid.UUID(sys.argv[1]), sys.argv[2])
