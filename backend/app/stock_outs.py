"""Remembers the days a part had no stock in a branch. Forecasts read those days as "unknown
demand", not "nobody wanted it". Real shops only: the demo shop comes with its own stock-outs.

Checked every hour and after each parts/stock import. Each day is saved once: a part still empty
the next day extends its stock-out period instead of starting a new one.
"""

import asyncio
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Organization, Part, StockLevel, StockOut

log = logging.getLogger(__name__)
CHECK_EVERY_SECONDS = 3600


def record_stock_outs(db: Session, organization_id: uuid.UUID, today: date) -> int:
    """Saves `today` as a stock-out day for every active part at 0 stock in a branch. Returns how
    many part-branches are out today. The caller commits."""
    empty = db.execute(
        select(StockLevel.part_id, StockLevel.branch_id)
        .join(Part, Part.id == StockLevel.part_id)
        .where(StockLevel.organization_id == organization_id, StockLevel.quantity <= 0, Part.is_active)
    ).all()
    recent = {
        (out.part_id, out.branch_id): out
        for out in db.scalars(
            select(StockOut)
            .where(StockOut.organization_id == organization_id, StockOut.last_day >= today - timedelta(days=1))
            .order_by(StockOut.last_day)
        )
    }
    for part_id, branch_id in empty:
        out = recent.get((part_id, branch_id))
        if out is not None and out.last_day >= today:
            continue
        if out is not None:  # still empty since yesterday
            out.last_day = today
        else:
            db.add(StockOut(organization_id=organization_id, part_id=part_id, branch_id=branch_id, first_day=today, last_day=today))
    return len(empty)


def record_stock_outs_now(organization_id: uuid.UUID) -> None:
    """For one shop, in its own session (used after an import)."""
    with SessionLocal() as db:
        record_stock_outs(db, organization_id, date.today())
        db.commit()


def record_all_stock_outs(today: date) -> None:
    with SessionLocal() as db:
        for shop_id in db.scalars(select(Organization.id).where(~Organization.is_demo)).all():
            record_stock_outs(db, shop_id, today)
        db.commit()


async def keep_recording_stock_outs() -> None:
    """Runs while the server is up. Hourly, so a day is never missed even after a restart."""
    while True:
        try:
            await asyncio.to_thread(record_all_stock_outs, date.today())
        except Exception:
            log.exception("Recording stock-outs failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
