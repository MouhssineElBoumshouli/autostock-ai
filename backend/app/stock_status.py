"""How healthy a part's stock is. One definition, used by the list, the stat cards and the detail.

- Out of stock: nothing on hand.
- Low stock: on hand is at or below the part's minimum stock level.
- Healthy: above the minimum (or no minimum set and some on hand).
- Inactive: the part is switched off.
- Dead stock: has stock, but no sale in the last 90 days.

A fifth status, "running_out", overrides "healthy" when the forecast says the part will run out
within 14 days even though it is above its minimum. Out of stock and low stock still win over it;
it needs the forecast, so it is applied on top of this module's statuses (see app.runs_out).
"""

import uuid
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import Select, and_, case, exists, func, not_, select
from sqlalchemy.sql import ColumnElement

from app.models import Part, SaleLine, StockLevel
from app.shop_day import shop_today

StockStatus = Literal["healthy", "low", "out", "inactive", "running_out"]
DEAD_AFTER_DAYS = 90


def quantity_on_hand(organization_id: uuid.UUID, branch_id: uuid.UUID | None = None, part_ids: Select | None = None):
    """A subquery: total on hand per part (in one branch, or all branches), for every part or only
    the parts `part_ids` selects (a search's matches: a big shop doesn't add up all its parts)."""
    query = select(StockLevel.part_id, func.sum(StockLevel.quantity).label("quantity")).where(
        StockLevel.organization_id == organization_id
    )
    if branch_id:
        query = query.where(StockLevel.branch_id == branch_id)
    if part_ids is not None:
        query = query.where(StockLevel.part_id .in_(part_ids))
    return query.group_by(StockLevel.part_id).subquery()


def status_of(quantity: ColumnElement) -> ColumnElement:
    return case(
        (not_(Part.is_active), "inactive"),
        (quantity <= 0, "out"),
        (and_(Part.min_stock > 0, quantity <= Part.min_stock), "low"),
        else_="healthy",
    )


def is_dead(quantity: ColumnElement, branch_id: uuid.UUID | None = None, today: date | None = None) -> ColumnElement:
    since = (today or shop_today()) - timedelta(days=DEAD_AFTER_DAYS)
    # The shop too, though a part's sales are always its shop's: it lets PostgreSQL use the
    # (shop, part, day) index instead of reading every sales line.
    recent_sale = select(SaleLine.id).where(
        SaleLine.organization_id == Part.organization_id, SaleLine.part_id == Part.id, SaleLine.sold_on >= since
    )
    if branch_id:
        recent_sale = recent_sale.where(SaleLine.branch_id == branch_id)
    return and_(Part.is_active, quantity > 0, not_(exists(recent_sale)))


def status_for(is_active: bool, quantity: int, min_stock: int) -> StockStatus:
    """The same rules in plain Python, for one part."""
    if not is_active:
        return "inactive"
    if quantity <= 0:
        return "out"
    if min_stock > 0 and quantity <= min_stock:
        return "low"
    return "healthy"
