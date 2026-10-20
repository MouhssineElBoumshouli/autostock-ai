"""One shop's daily sales and stock, as tables (one row per part in a branch, one column per day)."""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.forecast.engine import BASELINE, LOCAL_METHODS
from app.forecast.history import demand_matrix
from app.models import Forecast, Organization, Part, SaleLine, StockHistory, StockOut


@dataclass
class ShopData:
    keys: list[tuple[uuid.UUID, uuid.UUID]]  # (part_id, branch_id) of each row
    first_day: date
    sold: np.ndarray  # pieces sold each day (returns taken off, never below 0)
    demand: np.ndarray  # the same, with NaN on days demand is unknown (empty shelf, before the first sale)
    shelf: np.ndarray  # stock at the end of each day, NaN when not known
    price: np.ndarray  # sale price in centimes (0 when unknown)
    cost: np.ndarray  # unit cost in centimes (0 when unknown)
    methods: list[str]  # the forecast method each row uses for 7 days
    currency: str
    method_tables: dict[str, np.ndarray] = field(default_factory=dict)

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

    def forecast_table(self, method: str) -> np.ndarray:
        """Column t: the daily rate the method expected from day t on, using only days before t."""
        if method not in self.method_tables:
            self.method_tables[method] = LOCAL_METHODS[method](self.demand)
        return self.method_tables[method]

    @cached_property
    def stock_changed_days(self) -> np.ndarray:
        """True on days some part's stock changed anywhere in the shop."""
        steps = np.diff(self.shelf, axis=1)
        changed = np.zeros(self.shelf.shape[1], dtype=bool)
        changed[1:] = ((steps != 0) & ~np.isnan(steps)).any(axis=0)
        return changed


def load_shop_data(db: Session, organization_id: uuid.UUID, today: date) -> ShopData | None:
    """Every active part in every branch with sales or stock history up to `today`."""
    sales = db.execute(
        select(SaleLine.part_id, SaleLine.branch_id, SaleLine.sold_on, func.sum(SaleLine.quantity))
        .join(Part, Part.id == SaleLine.part_id)
        .where(SaleLine.organization_id == organization_id, SaleLine.sold_on <= today, Part.is_active)
        .group_by(SaleLine.part_id, SaleLine.branch_id, SaleLine.sold_on)
    ).all()
    stock = db.execute(
        select(StockHistory.part_id, StockHistory.branch_id, StockHistory.day, StockHistory.quantity)
        .join(Part, Part.id == StockHistory.part_id)
        .where(StockHistory.organization_id == organization_id, StockHistory.day <= today, Part.is_active)
        .order_by(StockHistory.day)
    ).all()
    if not sales and not stock:
        return None
    keys = sorted({(r[0], r[1]) for r in sales} | {(r[0], r[1]) for r in stock})
    index = {key: i for i, key in enumerate(keys)}
    first_day = min(r[2] for r in [*sales, *stock])
    days = (today - first_day).days + 1

    sold = np.zeros((len(keys), days))
    for part, branch, day, quantity in sales:
        sold[index[(part, branch)], (day - first_day).days] += quantity
    sold = np.clip(sold, 0, None)
    outs = db.execute(
        select(StockOut.part_id, StockOut.branch_id, StockOut.first_day, StockOut.last_day).where(StockOut.organization_id == organization_id)
    ).all()
    demand = demand_matrix(
        [(index[(part, branch)], day, int(quantity)) for part, branch, day, quantity in sales],
        [(index[(part, branch)], first, last) for part, branch, first, last in outs if (part, branch) in index],
        len(keys),
        first_day,
        days,
    )
    shelf = np.full((len(keys), days), np.nan)
    for part, branch, day, quantity in stock:  # oldest first: each change holds until the next one
        shelf[index[(part, branch)], (day - first_day).days :] = quantity

    parts = {p.id: p for p in db.scalars(select(Part).where(Part.organization_id == organization_id))}
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
        shelf=shelf,
        price=np.array([parts[p].sale_price or 0 for p, _ in keys]),
        cost=np.array([parts[p].unit_cost or 0 for p, _ in keys]),
        methods=[replayable_method(stored.get(key)) for key in keys],
        currency=db.scalar(select(Organization.currency).where(Organization.id == organization_id)) or "MAD",
    )


def replayable_method(method: str | None) -> str:
    """Alerts must ask "what did the forecast expect for last week?" every day, so they replay the
    forecast method on past weeks. The simple methods replay in a blink. Boosting needs a model
    trained for each past week, too slow to redo daily, so its parts use the 4-week average (the
    baseline boosting had to beat to be chosen). Parts without a forecast yet use it too."""
    return method if method in LOCAL_METHODS else BASELINE
