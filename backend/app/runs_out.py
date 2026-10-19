"""How soon a part's stock is expected to run out, from its 30-day forecast.

Days = how many days the quantity on hand covers at the forecast's daily rate.
None means "over 60 days" (including parts with no expected sales at all)."""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.sql import Select

from app.models import Forecast

HORIZON_DAYS = 30
SHOWN_UP_TO_DAYS = 60
RUNNING_OUT_WITHIN_DAYS = 14


def expected_30d_subquery(organization_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> Select:
    """Pieces expected to sell over the next 30 days, per part (in one branch, or all branches)."""
    query = select(Forecast.part_id, func.sum(Forecast.quantity).label("expected_30d")).where(
        Forecast.organization_id == organization_id, Forecast.horizon_days == HORIZON_DAYS
    )
    if branch_id:
        query = query.where(Forecast.branch_id == branch_id)
    return query.group_by(Forecast.part_id).subquery()


def runs_out_days_expr(quantity: ColumnElement, expected_30d: ColumnElement) -> ColumnElement:
    """Days of cover left, uncapped (used for sorting; the website shows "over 60 days" past 60)."""
    return (quantity * HORIZON_DAYS) / expected_30d


def shown_runs_out_days(raw_days: float | None) -> int | None:
    """None ("over 60 days") when there is no expected demand or the cover is beyond what we show."""
    if raw_days is None or raw_days > SHOWN_UP_TO_DAYS:
        return None
    return max(round(raw_days), 1)
