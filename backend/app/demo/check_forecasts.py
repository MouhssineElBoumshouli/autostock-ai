"""Checks the forecast engine on the demo shop, where the true future demand is known.

Run inside Docker (after app.demo.demo_shop):  docker compose exec api python -m app.demo.check_forecasts
These are scores on made-up data, not the accuracy a real shop will see.
"""

from collections import Counter, defaultdict
from datetime import timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import select

from app.db import SessionLocal
from app.forecast.engine import BASELINE, HORIZONS, SeriesForecast, forecast_all
from app.forecast.run import ShopDemand, load_demand, run_forecasts
from app.models import DemoTrueDemand, Organization


def main() -> None:
    with SessionLocal() as db:
        shop_id = db.scalar(select(Organization.id).where(Organization.is_demo))
        if shop_id is None:
            raise SystemExit("No demo shop. Run: python -m app.demo.demo_shop")
        started = perf_counter()
        run = run_forecasts(db, shop_id, "manual")
        db.commit()
        print(f"Full run (read sales, forecast, save): {perf_counter() - started:.1f} s for {run.series_count} part-branch pairs")

        shop = load_demand(db, shop_id)
        results = forecast_all(shop.demand, shop.first_day)
        truth = true_future_totals(db, shop)

        # Same engine, but stock-out days counted as zero sales: shows what the cleaning is worth.
        uncleaned = forecast_all(np.nan_to_num(shop.demand), shop.first_day)

    for horizon in HORIZONS:
        mine = [r for r in results if r.horizon == horizon]
        print(f"\n=== Next {horizon} days ===")
        print_wins(mine)
        print_backtest(mine)
        print_truth(mine, truth[horizon])
        raw = [r for r in uncleaned if r.horizon == horizon]
        print(f"  without cleaning stock-out days, chosen WAPE vs truth: {truth_wape(raw, truth[horizon], None):.3f}")


def true_future_totals(db, shop: ShopDemand) -> dict[int, np.ndarray]:
    index = {key: i for i, key in enumerate(shop.keys)}
    totals = {h: np.zeros(len(shop.keys)) for h in HORIZONS}
    rows = db.execute(
        select(DemoTrueDemand.part_id, DemoTrueDemand.branch_id, DemoTrueDemand.day, DemoTrueDemand.quantity).where(
            DemoTrueDemand.day > shop.last_day
        )
    )
    for part, branch, day, quantity in rows:
        if (part, branch) in index:
            for h in HORIZONS:
                if day <= shop.last_day + timedelta(days=h):
                    totals[h][index[(part, branch)]] += quantity
    return totals


def print_wins(results: list[SeriesForecast]) -> None:
    by_type = defaultdict(Counter)
    widen = {}
    for r in results:
        by_type[r.demand_type][r.method] += 1
        widen[r.demand_type] = r.widen
    for kind, wins in sorted(by_type.items()):
        used = ", ".join(f"{m} {n}" for m, n in wins.most_common())
        print(f"  {kind:8} ({sum(wins.values()):3}): {used}; ranges widened x{widen[kind]}")


def print_backtest(results: list[SeriesForecast]) -> None:
    tested = [r for r in results if r.method_error is not None and r.baseline_error is not None and r.method_wape]
    sold = sum(r.method_error / r.method_wape for r in tested)
    chosen = sum(r.method_error for r in tested) / sold
    base = sum(r.baseline_error for r in tested) / sold
    print(f"  backtest WAPE (in-sample, flatters the chosen): chosen {chosen:.3f} vs baseline {base:.3f}")


def truth_wape(results: list[SeriesForecast], truth: np.ndarray, method: str | None) -> float:
    forecast = np.array([r.every_method[method] if method else r.quantity for r in results])
    actual = truth[[r.row for r in results]]
    return float(np.abs(forecast - actual).sum() / actual.sum())


def print_truth(results: list[SeriesForecast], truth: np.ndarray) -> None:
    print(f"  vs TRUE future demand, WAPE: chosen {truth_wape(results, truth, None):.3f}, "
          f"baseline {truth_wape(results, truth, BASELINE):.3f}")
    for method in results[0].every_method:
        print(f"    everyone on {method:22} {truth_wape(results, truth, method):.3f}")
    by_type = defaultdict(list)
    for r in results:
        by_type[r.demand_type].append(r)
    for kind, group in sorted(by_type.items()):
        print(f"    {kind:8} chosen {truth_wape(group, truth, None):.3f} vs baseline {truth_wape(group, truth, BASELINE):.3f}")
    inside = np.mean([r.low <= truth[r.row] <= r.high for r in results])
    print(f"  true demand inside the low-high range: {100 * inside:.0f}% of part-branch pairs")


if __name__ == "__main__":
    main()
