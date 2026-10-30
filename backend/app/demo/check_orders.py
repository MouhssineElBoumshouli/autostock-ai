"""Proof for "what to order": replays the demo shop's last 6 months day by day, for three methods
at several settings, and compares them at the same money in stock.

- AutoStock: once a week, its forecasts + order math, at service targets 80-98%.
- Textbook reorder point (no AI): once a week, the same order math fed with "average of the last
  4 weeks" and the spread of weekly sales, at the same service targets.
- The usual minimum rule: every day, below the minimum -> order back up to 1.5x, 2x, 3x or 4x it.
Same true demand, starting stock, supplier delivery times and pack sizes for all. Every suggested
line is approved as is. Forecasts are made once per week of the replay from the demo's recorded
sales (with its own empty-shelf days unknown) and reused for every service target.

The full demo shop is ~2,000 parts x 3 branches; replaying 6 months for all of them here would
take over an hour, so this script samples about 1 in 3 part-branch pairs, keeping each demand
type's (smooth/erratic/slow/lumpy/no_sales) share the same as the full catalog (app/demo/sampling.py).

It builds a fresh demo shop (same recipe and seed as app.demo.demo_shop) inside a transaction that
is rolled back at the end, so the real demo shop and its login are never touched and the numbers
are the same every time.

Run inside Docker:  docker compose exec api python -m app.demo.check_orders
These are results on made-up data, not what a real shop will see.
"""

from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import select

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.demo.production_guard import refuse_demo_in_production
from app.demo.sampling import SAMPLE_EVERY, sample_every_third
from app.forecast.engine import forecast_all
from app.forecast.run import ShopDemand, load_demand
from app.models import DemoTrueDemand, Part, Supplier
from app.ordering.replay import ReplayResult, four_week_forecasts, minimum_rule, replay, weekly_rule
from app.ordering.run import DEFAULT_DELIVERY_DAYS
from app.ordering.suggest import REVIEW_DAYS, HorizonForecast

LAST_DAY = date(2026, 10, 18)  # fixed, so the result can be checked again
REPLAY_DAYS = 182  # 6 months
SERVICE_TARGETS = (0.80, 0.85, 0.90, 0.95, 0.98)
MINIMUM_MULTIPLES = (1.5, 2.0, 3.0, 4.0)


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day=LAST_DAY)
        db.flush()
        full = load_demand(db, shop.id)
        start = full.demand.shape[1] - REPLAY_DAYS
        sample = sample_every_third(full.demand[:, :start])
        history = ShopDemand([full.keys[i] for i in sample], full.demand[sample], full.first_day, full.last_day)
        print(f"Sampling 1 in {SAMPLE_EVERY} by demand type: {len(sample)} of {len(full.keys)} part-branch pairs.")
        rows = len(history.keys)
        index = {key: i for i, key in enumerate(history.keys)}
        first_replayed = history.first_day + timedelta(days=start)

        truth = np.zeros((rows, REPLAY_DAYS))
        for part, branch, day, quantity in db.execute(
            select(DemoTrueDemand.part_id, DemoTrueDemand.branch_id, DemoTrueDemand.day, DemoTrueDemand.quantity).where(
                DemoTrueDemand.organization_id == shop.id, DemoTrueDemand.day >= first_replayed, DemoTrueDemand.day <= LAST_DAY
            )
        ):
            if (part, branch) in index:
                truth[index[(part, branch)], (day - first_replayed).days] = quantity

        parts = {row.id: row for row in db.execute(
            select(Part.id, Part.min_stock, Part.pack_size, Part.unit_cost, Part.sale_price, Supplier.delivery_days)
            .outerjoin(Supplier, Supplier.id == Part.supplier_id).where(Part.organization_id == shop.id)
        )}
        db.rollback()  # the real demo shop is back as it was

    info = [parts[part_id] for part_id, _ in history.keys]
    delivery = np.array([p.delivery_days if p.delivery_days is not None else DEFAULT_DELIVERY_DAYS for p in info])
    packs = np.array([p.pack_size for p in info])
    cost = np.array([p.unit_cost or 0 for p in info], dtype=float)
    price = np.array([p.sale_price or 0 for p in info], dtype=float)
    past = history.demand[:, :start]
    minimums = branch_minimums(history.keys, [p.min_stock for p in info], past)
    start_stock = np.round(1.5 * minimums)  # halfway between the rule's reorder point and its target

    print(f"Demo shop (measured on a 1-in-{SAMPLE_EVERY} sample): {rows} part-branch pairs, replaying {first_replayed} to {LAST_DAY} ({REPLAY_DAYS} days).")
    began = perf_counter()
    review_days = range(0, REPLAY_DAYS, REVIEW_DAYS)
    autostock = {day: engine_forecasts(history.demand[:, : start + day], history.first_day) for day in review_days}
    print(f"  AutoStock forecasts for {len(review_days)} weeks: {perf_counter() - began:.0f} s (made once, reused for every target)")
    textbook = {day: four_week_forecasts(history.demand[:, : start + day]) for day in review_days}

    def run(rule) -> ReplayResult:
        return replay(truth, past, start_stock, delivery, rule, cost, price)

    began = perf_counter()
    curves = {
        "AutoStock": [(f"{t:.0%}", run(weekly_rule(lambda today: autostock[today.day], packs, delivery, t))) for t in SERVICE_TARGETS],
        "Textbook reorder point": [(f"{t:.0%}", run(weekly_rule(lambda today: textbook[today.day], packs, delivery, t))) for t in SERVICE_TARGETS],
        "Minimum rule": [(f"up to {m}x", run(minimum_rule(minimums, packs, m))) for m in MINIMUM_MULTIPLES],
    }
    print(f"  {sum(len(c) for c in curves.values())} replays: {perf_counter() - began:.0f} s")

    wanted = truth.sum()
    print(f"\n{'method':24} {'setting':10} {'stock (MAD)':>12} {'lost':>6} {'lost pcs':>9} {'days out':>9}")
    for name, points in curves.items():
        for setting, r in points:
            print(f"{name:24} {setting:10} {r.average_stock_value / 100:12,.0f} {100 * r.lost_pieces / wanted:5.1f}% "
                  f"{r.lost_pieces:9,} {r.days_out:9,}")

    print("\nAt the same money in stock as each AutoStock point (other curves interpolated between their points):")
    for setting, mine in curves["AutoStock"]:
        for other in ("Textbook reorder point", "Minimum rule"):
            lost = lost_at_same_stock(curves[other], mine.average_stock_value)
            if lost is None:
                print(f"  AutoStock {setting} ({mine.average_stock_value / 100:,.0f} MAD) vs {other}: outside its tested range")
            else:
                print(f"  AutoStock {setting} ({mine.average_stock_value / 100:,.0f} MAD) vs {other}: "
                      f"{lost - mine.lost_pieces:,.0f} fewer lost pieces ({100 * lost / wanted:.1f}% -> {100 * mine.lost_pieces / wanted:.1f}%)")
    print(f"\nTotal time {perf_counter() - started:.0f} s. Made-up data: not what a real shop will see.")


def engine_forecasts(seen: np.ndarray, first_day: date) -> list[tuple[HorizonForecast, ...]]:
    """The forecast engine on history up to a day; rows with nothing known yet get no forecast."""
    known = ~np.isnan(seen).all(axis=1)
    found: list[list[HorizonForecast]] = [[] for _ in range(len(seen))]
    use = np.flatnonzero(known)
    for r in forecast_all(seen[known], first_day):
        found[use[r.row]].append(HorizonForecast(r.horizon, r.quantity, r.high))
    return [tuple(f) for f in found]


def lost_at_same_stock(points: list[tuple[str, ReplayResult]], stock_value: float) -> float | None:
    """Lost pieces a method would have at `stock_value`, read off the straight lines between its
    tested points. None outside the range it was tested on (no guessing beyond it)."""
    ordered = sorted((r.average_stock_value, r.lost_pieces) for _, r in points)
    stocks, losts = zip(*ordered)
    if not stocks[0] <= stock_value <= stocks[-1]:
        return None
    return float(np.interp(stock_value, stocks, losts))


def branch_minimums(keys: list, part_minimums: list[int], past: np.ndarray) -> np.ndarray:
    """The demo's minimum is per part (all branches together). Each branch gets its share, by how
    many it sold before the replay, and at least 1."""
    rates = np.nansum(past, axis=1)
    totals: dict = {}
    for (part, _), rate in zip(keys, rates):
        totals[part] = totals.get(part, 0.0) + rate
    return np.array([
        max(1, round(minimum * (rate / totals[part] if totals[part] > 0 else 1 / 3)))
        for (part, _), minimum, rate in zip(keys, part_minimums, rates)
    ])


if __name__ == "__main__":
    main()
