"""Saves each part's stock day by day (only on days it changes), so alerts can compare stock with
sales. Runs with the stock-out check: every hour and after each parts/stock import."""

import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Part, StockHistory, StockLevel


def record_stock_history(db: Session, organization_id: uuid.UUID, today: date) -> int:
    """Saves today's stock for every active part whose number changed. Returns how many. The caller commits."""
    newest = (
        select(StockHistory.part_id, StockHistory.branch_id, func.max(StockHistory.day).label("day"))
        .where(StockHistory.organization_id == organization_id)
        .group_by(StockHistory.part_id, StockHistory.branch_id)
        .subquery()
    )
    # Plain rows, not full objects: a big shop has 150,000 part-branches to compare every hour.
    saved = {
        (row.part_id, row.branch_id): row
        for row in db.execute(
            select(StockHistory.id, StockHistory.part_id, StockHistory.branch_id, StockHistory.day, StockHistory.quantity)
            .join(
                newest,
                (StockHistory.part_id == newest.c.part_id)
                & (StockHistory.branch_id == newest.c.branch_id)
                & (StockHistory.day == newest.c.day),
            )
            .where(StockHistory.organization_id == organization_id)
        )
    }
    levels = db.execute(
        select(StockLevel.part_id, StockLevel.branch_id, StockLevel.quantity)
        .join(Part, Part.id == StockLevel.part_id)
        .where(StockLevel.organization_id == organization_id, Part.is_active)
    ).all()
    changed = 0
    for part_id, branch_id, quantity in levels:
        last = saved.get((part_id, branch_id))
        if last is not None and last.quantity == quantity:
            continue
        changed += 1
        if last is not None and last.day == today:  # changed again later the same day: keep the end-of-day number
            db.execute(update(StockHistory).where(StockHistory.id == last.id).values(quantity=quantity))
        else:
            db.add(StockHistory(organization_id=organization_id, part_id=part_id, branch_id=branch_id, day=today, quantity=quantity))
    db.flush()
    return changed
