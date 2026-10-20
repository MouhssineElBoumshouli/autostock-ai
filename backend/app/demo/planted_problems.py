"""Problems put in the demo shop on purpose, with their true dates, so we can measure the alerts:
sales spikes and drops, stock frozen while sales continue (like theft or a counting error), sales
recorded while the stock said 0, and negative stock. Also the stock on the shelf day by day.

Demo shops only. All planted problems start in the last weeks of the history, so a replay of the
alerts over those weeks can tell how many were caught and how many days it took.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from app.models import Part

MIN_HISTORY_DAYS = 120  # shorter demo histories get no planted problems
STOCK_HISTORY_DAYS = 120  # days of stock history saved for the demo
# How many of each kind, for a full demo (about 600 parts x branches). Smaller demos get fewer.
TARGETS = {"sales_spike": 15, "sales_drop": 15, "stock_frozen": 10, "sold_at_zero": 10, "negative_stock": 4}
FULL_DEMO_SERIES = 600
# Spikes and drops are planted only where a week sells enough to judge: the alerts ignore slower
# parts on purpose (a week of 0 or a double is normal chance for them).
SALES_KIND_MIN_WEEKLY = 8
STOCK_KIND_MIN_WEEKLY = 3
RECENT_DAYS = 56  # weeks used to judge how much a series sells
CLEAN_DAYS = 70  # planted only where the shelf was never empty in these last days


@dataclass
class Planted:
    kind: str
    first: int  # day index in the history, first and last day included
    last: int
    details: dict


@dataclass
class DemoSeries:
    """One part in one branch while the demo is made."""

    part: Part
    branch_id: object
    sold: np.ndarray  # pieces sold each history day
    wanted: np.ndarray  # true demand: the history days, then the future days
    out_days: np.ndarray  # True on days the shelf was empty
    quantity: int = 0  # on the shelf now
    problem: Planted | None = field(default=None)


def plant_problems(rng: np.random.Generator, series: list[DemoSeries]) -> list[DemoSeries]:
    """Gives some series one problem each and changes their sales to match. Returns those series."""
    if not series or len(series[0].sold) < MIN_HISTORY_DAYS:
        return []
    weekly = {id(s): s.sold[-RECENT_DAYS:].sum() * 7 / RECENT_DAYS for s in series}
    clean = [s for s in series if not s.out_days[-CLEAN_DAYS:].any()]
    order = rng.permutation(len(clean))
    pool = [clean[i] for i in order]
    scale = min(1.0, len(series) / FULL_DEMO_SERIES)

    chosen = []
    for kind, target in TARGETS.items():
        floor = SALES_KIND_MIN_WEEKLY if kind in ("sales_spike", "sales_drop") else STOCK_KIND_MIN_WEEKLY
        fits = [s for s in pool if s.problem is None and weekly[id(s)] >= floor and (kind != "stock_frozen" or s.quantity > 0)]
        for s in fits[: max(1, round(target * scale))]:
            s.problem = PLANTERS[kind](rng, s)
            chosen.append(s)
    return chosen


def _spike(rng: np.random.Generator, s: DemoSeries) -> Planted:
    last_index = len(s.sold) - 1
    first = int(rng.integers(last_index - 48, last_index - 9))
    last = min(first + int(rng.integers(7, 15)) - 1, last_index)
    factor = round(float(rng.uniform(2.5, 4.0)), 2)
    daily = s.sold[-RECENT_DAYS:].mean()
    extra = rng.poisson((factor - 1) * daily, last - first + 1)
    _change_sales(s, first, s.sold[first : last + 1] + extra)
    return Planted("sales_spike", first, last, {"times_usual": factor})


def _drop(rng: np.random.Generator, s: DemoSeries) -> Planted:
    last_index = len(s.sold) - 1
    first = int(rng.integers(last_index - 48, last_index - 9))
    last = min(first + int(rng.integers(7, 15)) - 1, last_index)
    keep = round(float(rng.uniform(0.0, 0.25)), 2)
    _change_sales(s, first, rng.binomial(s.sold[first : last + 1].astype(int), keep))
    return Planted("sales_drop", first, last, {"share_kept": keep})


def _frozen(rng: np.random.Generator, s: DemoSeries) -> Planted:
    """From `first` on, sales are no longer taken off the recorded stock (see stock_by_day)."""
    last_index = len(s.sold) - 1
    first = int(rng.integers(last_index - 45, last_index - 15))
    return Planted("stock_frozen", first, last_index, {"stuck_at": s.quantity})


def _sold_at_zero(rng: np.random.Generator, s: DemoSeries) -> Planted:
    """A few days of real sales while the recorded stock said 0 (see stock_by_day)."""
    last_index = len(s.sold) - 1
    first = int(rng.integers(last_index - 45, last_index - 4))
    last = first + int(rng.integers(2, 5)) - 1
    days = s.sold[first : last + 1]
    _change_sales(s, first, np.maximum(days, rng.integers(1, 4, len(days))))
    return Planted("sold_at_zero", first, last, {})


def _negative(rng: np.random.Generator, s: DemoSeries) -> Planted:
    last_index = len(s.sold) - 1
    first = int(rng.integers(last_index - 30, last_index - 2))
    details = {"first_quantity": -int(rng.integers(1, 4)), "quantity_before": s.quantity}
    return Planted("negative_stock", first, last_index, details)


PLANTERS = {
    "sales_spike": _spike,
    "sales_drop": _drop,
    "stock_frozen": _frozen,
    "sold_at_zero": _sold_at_zero,
    "negative_stock": _negative,
}


def _change_sales(s: DemoSeries, first: int, new: np.ndarray) -> None:
    """Planted sales are real demand too, so true demand moves by the same amount."""
    days = slice(first, first + len(new))
    s.wanted[days] += new - s.sold[days]
    s.sold[days] = new


def stock_by_day(rng: np.random.Generator, s: DemoSeries) -> np.ndarray:
    """Stock at the end of each of the last STOCK_HISTORY_DAYS days, worked backward from today's
    stock: yesterday = today + what sold today, with a delivery whenever that would pass a full
    shelf. Empty-shelf days stay at 0. Planted stock problems are applied last. May change
    `s.quantity` (negative stock)."""
    days = len(s.sold)
    start = days - STOCK_HISTORY_DAYS
    counted = s.sold.copy()
    p = s.problem
    if p and p.kind == "stock_frozen":
        counted[p.first :] = 0  # sales no longer reach the recorded stock
    daily = max(float(s.sold[start:].mean()), 0.05)
    full, refill_point = max(s.quantity, round(daily * 45), 3), max(1, round(daily * 7))

    stock = np.zeros(days, dtype=int)
    stock[-1] = s.quantity
    for d in range(days - 1, start, -1):
        before = stock[d] + counted[d]
        if s.out_days[d - 1]:
            stock[d - 1] = 0
        elif before <= full:
            stock[d - 1] = before
        else:  # a delivery came that day
            stock[d - 1] = int(rng.integers(1, refill_point + 1))
            if stock[d - 1] == stock[d] and counted[d] > 0:
                # Real deliveries almost never match a day's sales to the piece; if they did here
                # (common for slow parts, whose refill point is 1), the stock would look frozen.
                stock[d - 1] += 1

    if p and p.kind == "sold_at_zero":
        stock[p.first - 1 : p.last + 1] = 0
    if p and p.kind == "negative_stock":
        stock[p.first] = p.details["first_quantity"]
        for d in range(p.first + 1, days):
            stock[d] = stock[d - 1] - s.sold[d]
        s.quantity = int(stock[-1])
    return stock[start:]


def stock_history_rows(rng: np.random.Generator, s: DemoSeries, first_day: date) -> list[tuple]:
    """(part, branch, day, quantity) for the first saved day and every day the stock changed."""
    stock = stock_by_day(rng, s)
    start_day = first_day + timedelta(days=len(s.sold) - STOCK_HISTORY_DAYS)
    return [
        (s.part.id, s.branch_id, start_day + timedelta(days=i), int(q))
        for i, q in enumerate(stock)
        if i == 0 or q != stock[i - 1]
    ]


def planted_rows(s: DemoSeries, first_day: date) -> tuple:
    p = s.problem
    return (s.part.id, s.branch_id, p.kind, first_day + timedelta(days=p.first), first_day + timedelta(days=p.last), p.details)
