"""One shop's daily sales and stock, as tables (one row per part in a branch, one column per day)."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cached_property

import numpy as np
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session

from app.forecast.engine import BASELINE, LOCAL_METHODS, local_forecasts
from app.forecast.history import (
    DAY_ZERO,
    READ_AT_A_TIME,
    DaySales,
    Key,
    demand_matrix,
    first_and_last_day,
    read_daily_sales,
    sales_table,
)
from app.models import Forecast, Organization, Part, StockHistory, StockOut


# Whole numbers of pieces (and NaN) fit exactly in 4-byte decimals up to 16 million: half the
# memory of the usual 8 bytes, for tables a big shop has 150,000 rows x 2 years of.
WHOLE_PIECES = np.float32


@dataclass
class ShopData:
    keys: list[tuple[uuid.UUID, uuid.UUID]]  # (part_id, branch_id) of each row
    first_day: date
    sold: np.ndarray  # pieces sold each day (returns taken off, never below 0)
    demand: np.ndarray  # the same, with NaN on days demand is unknown (empty shelf, before the first sale)
    shelf: np.ndarray  # stock at the end of each day, NaN when not known
    # `sold` and `shelf` are WHOLE_PIECES; `demand` stays 8-byte, as the forecast methods expect.
    price: np.ndarray  # sale price in centimes (0 when unknown)
    cost: np.ndarray  # unit cost in centimes (0 when unknown)
    methods: list[str]  # the forecast method each row uses for 7 days
    currency: str

    def day(self, index: int) -> date:
        return self.first_day + timedelta(days=index)

    def last_sales_index(self, up_to: int) -> int | None:
        """The newest day up to `up_to` with a sale anywhere in the shop: sales after it are not
        imported yet, so the alerts judge the week that ends there."""
        days = np.flatnonzero(self.sold[:, : up_to + 1].sum(axis=0) > 0)
        return int(days[-1]) if len(days) else None

    def money_per_piece(self, row: int, sales: bool) -> int:
        """Sale price for sales problems, cost for stock problems; the other one if missing."""
        first, second = (self.price[row], self.cost[row]) if sales else (self.cost[row], self.price[row])
        return int(first or second)

    def forecasts_from(self, method: str, days: list[int]) -> np.ndarray:
        """Column j: the daily rate the method expected from day days[j] on, using only days before it."""
        return local_forecasts(self.demand, days, [method])[method]

    @cached_property
    def stock_changed_days(self) -> np.ndarray:
        """True on days some part's stock changed anywhere in the shop."""
        steps = np.diff(self.shelf, axis=1)
        changed = np.zeros(self.shelf.shape[1], dtype=bool)
        changed[1:] = ((steps != 0) & ~np.isnan(steps)).any(axis=0)
        return changed


def load_shop_data(db: Session, organization_id: uuid.UUID, today: date) -> ShopData | None:
    """Every active part in every branch with sales or stock history up to `today`."""
    sales = read_daily_sales(db, organization_id, until=today)
    stock = _read_stock_changes(db, organization_id, today)
    if not sales and not stock:
        return None
    keys = sorted(set(sales) | set(stock))
    index = {key: i for i, key in enumerate(keys)}
    first_day = min(first_and_last_day(table)[0] for table in (sales, stock) if table)
    days = (today - first_day).days + 1

    sold_and_returned = sales_table(sales, keys, first_day, days)
    sold = np.clip(sold_and_returned, 0, None, out=np.empty((len(keys), days), dtype=WHOLE_PIECES))
    outs = db.execute(
        select(StockOut.part_id, StockOut.branch_id, StockOut.first_day, StockOut.last_day).where(StockOut.organization_id == organization_id)
    ).all()
    demand = demand_matrix(
        sold_and_returned,
        [(index[(part, branch)], first, last) for part, branch, first, last in outs if (part, branch) in index],
        first_day,
    )
    del sold_and_returned  # freed before the shelf table is made: a big shop's tables are ~0.5-0.9 GB each
    prices = {
        part_id: (sale_price or 0, unit_cost or 0)
        for part_id, sale_price, unit_cost in db.execute(
            select(Part.id, Part.sale_price, Part.unit_cost).where(Part.organization_id == organization_id)
        )
    }
    stored = {
        (part, branch): method
        for part, branch, method in db.execute(
            select(Forecast.part_id, Forecast.branch_id, Forecast.method).where(
                Forecast.organization_id == organization_id, Forecast.horizon_days == 7
            )
        )
    }
    return ShopData(
        keys=keys,
        first_day=first_day,
        sold=sold,
        demand=demand,
        shelf=_shelf_table(stock, keys, first_day, days),
        price=np.array([prices[p][0] for p, _ in keys]),
        cost=np.array([prices[p][1] for p, _ in keys]),
        methods=[replayable_method(stored.get(key)) for key in keys],
        currency=db.scalar(select(Organization.currency).where(Organization.id == organization_id)) or "MAD",
    )


def _read_stock_changes(db: Session, organization_id: uuid.UUID, today: date) -> dict[Key, DaySales]:
    """Every saved stock change up to `today` of every active part in every branch, oldest first:
    (day numbers, quantity from that day on)."""
    day_number = StockHistory.day - literal(DAY_ZERO) + 1
    rows = db.execute(
        select(
            StockHistory.part_id,
            StockHistory.branch_id,
            func.array_agg(aggregate_order_by(day_number, StockHistory.day)),
            func.array_agg(aggregate_order_by(StockHistory.quantity, StockHistory.day)),
        )
        .join(Part, Part.id == StockHistory.part_id)
        .where(StockHistory.organization_id == organization_id, StockHistory.day <= today, Part.is_active)
        .group_by(StockHistory.part_id, StockHistory.branch_id)
        .execution_options(yield_per=READ_AT_A_TIME)
    )
    return {(part, branch): (np.array(days, dtype=np.int32), np.array(quantities, dtype=np.int32)) for part, branch, days, quantities in rows}


def _shelf_table(stock: dict[Key, DaySales], keys: list[Key], first_day: date, days: int) -> np.ndarray:
    """Stock at the end of each day: each change holds until the next one; NaN before the first."""
    shelf = np.full((len(keys), days), np.nan, dtype=WHOLE_PIECES)
    start = first_day.toordinal()
    for row, key in enumerate(keys):
        if key in stock:
            day_numbers, quantities = stock[key]
            change = np.full(days, -1)
            change[day_numbers - start] = np.arange(len(day_numbers))  # oldest first: the newest on a day wins
            change = np.maximum.accumulate(change)  # the newest change on or before each day
            shelf[row] = np.where(change >= 0, quantities[change], np.nan)
    return shelf


def replayable_method(method: str | None) -> str:
    """Alerts must ask "what did the forecast expect for last week?" every day, so they replay the
    forecast method on past weeks. The simple methods replay in a blink. Boosting needs a model
    trained for each past week, too slow to redo daily, so its parts use the 4-week average (the
    baseline boosting had to beat to be chosen). Parts without a forecast yet use it too."""
    return method if method in LOCAL_METHODS else BASELINE
