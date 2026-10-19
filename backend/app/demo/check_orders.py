"""Proof for "what to order": replays the demo shop's last 6 months day by day, twice.

(a) AutoStock: once a week, forecasts remade from what the shop had seen, every suggestion approved.
(b) The usual rule: every day, when stock (counting orders on their way) is below the minimum,
    order back up to twice the minimum.
Same true demand, same starting stock, same supplier delivery times, same pack sizes.

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
from app.forecast.engine import forecast_all
from app.forecast.run import load_demand
from app.models import DemoTrueDemand, Part, Supplier
from app.ordering.replay import ReplayResult, autostock_rule, minimum_rule, replay
from app.ordering.run import DEFAULT_DELIVERY_DAYS
from app.ordering.suggest import HorizonForecast

LAST_DAY = date(2026, 10, 18)  # fixed, so the result can be checked again
REPLAY_DAYS = 182  # 6 months


def main() -> None:
    started = perf_counter()
    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day=LAST_DAY)
        db.flush()
        history = load_demand(db, shop.id)
        rows = len(history.keys)
        index = {key: i for i, key in enumerate(history.keys)}
        start = history.demand.shape[1] - REPLAY_DAYS
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

    def forecaster(seen: np.ndarray) -> list[tuple[HorizonForecast, ...]]:
        known = ~np.isnan(seen).all(axis=1)
        found: list[list[HorizonForecast]] = [[] for _ in range(rows)]
        use = np.flatnonzero(known)
        for r in forecast_all(seen[known], history.first_day):
            found[use[r.row]].append(HorizonForecast(r.horizon, r.quantity, r.high))
        return [tuple(f) for f in found]

    print(f"Demo shop: {rows} part-branch pairs, replaying {first_replayed} to {LAST_DAY} ({REPLAY_DAYS} days).")
    results = {}
    for name, rule in (
        ("(a) AutoStock suggestions", autostock_rule(forecaster, packs, delivery)),
        ("(b) Below minimum -> back up to 2x minimum", minimum_rule(minimums, packs)),
    ):
        began = perf_counter()
        results[name] = replay(truth, past, start_stock, delivery, rule, cost, price)
        print(f"  {name}: replayed in {perf_counter() - began:.0f} s")
    print()
    for name, result in results.items():
        print_result(name, result, truth)
    print(f"\nTotal time {perf_counter() - started:.0f} s. Made-up data: not what a real shop will see.")


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


def print_result(name: str, r: ReplayResult, truth: np.ndarray) -> None:
    wanted = truth.sum()
    print(name)
    print(f"  days out of stock (part-branch days): {r.days_out}")
    print(f"  lost sales: {r.lost_pieces} pieces of {int(wanted)} wanted ({100 * r.lost_pieces / wanted:.1f}%), "
          f"{r.lost_money / 100:,.0f} MAD at sale price")
    print(f"  average money sitting in stock: {r.average_stock_value / 100:,.0f} MAD at cost")
    print(f"  order lines placed: {r.orders}")


if __name__ == "__main__":
    main()
