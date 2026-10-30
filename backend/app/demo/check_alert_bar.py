"""Checks the alerts' "how rare is rare enough" bar (app/alerts/sales_rules.py:
TARGET_FALSE_PER_WEEK / (judged parts x CHECKS_PER_WEEK x 2)): a fixed weekly false-alarm budget
for the whole shop, split across every part judged that day. A bigger catalog needs a stricter bar
per part — this, not noisier demand, is why the demo shop's spike/drop catch rate fell when step
8c-1 made it ~10x bigger (see docs/journey.md).

Prints the bar (at the rule's own target, 2/week) for the full catalog and the 1-in-3 sample
app.demo.check_alerts actually replays — then measures spike/drop catches and false alarms per
week on that same sample, but with the bar computed each day as if judging the FULL catalog (by
scaling the effective target so judged_sample/effective_target gives the same bar as
judged_full/target), at a few different weekly false-alarm budgets (edit TARGETS to try others).

Does not change app/alerts/sales_rules.py. It reads its constants and its own tiny "which parts
are judged today" calculation (the first loop of sales_problems) only to count rows for the bar;
every alert is still raised by the real, unmodified function.

Run inside Docker:  docker compose exec api python -m app.demo.check_alert_bar
"""

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import select

import app.alerts.sales_rules as sales_rules
from app.alerts.run import raise_alerts
from app.alerts.shop_data import ShopData, load_shop_data, replayable_method
from app.db import SessionLocal
from app.demo.check_alerts import _methods_before
from app.demo.demo_shop import create_demo_shop
from app.demo.production_guard import refuse_demo_in_production
from app.demo.sampling import sample_every_third
from app.models import Alert, DemoPlantedProblem

LAST_DAY = date(2026, 10, 18)
REPLAY_DAYS = 56
LATE_DAYS = 7
TARGETS = (2.0, 5.0, 10.0)
SALES_KINDS = ("sales_spike", "sales_drop")


def judged_count(data: ShopData, today: date) -> int:
    """How many rows sales_problems would judge for the week ending on `today` — the same
    eligibility check as its first loop (expected weekly sales high enough, enough past history),
    just counted instead of acted on."""
    end = data.last_sales_index((today - data.first_day).days)
    if end is None:
        return 0
    start = end - sales_rules.WEEK + 1
    origins = [start - sales_rules.WEEK * k for k in range(sales_rules.PAST_WEEKS, 0, -1) if start - sales_rules.WEEK * k >= 0]
    if len(origins) < sales_rules.MIN_PAST_WEEKS:
        return 0
    known = ~np.isnan(data.demand)
    week_known = np.column_stack([known[:, o : o + sales_rules.WEEK].sum(axis=1) for o in origins])
    count = 0
    for row, method in enumerate(data.methods):
        expected = float(data.forecast_table(method)[row, start]) * sales_rules.WEEK
        if expected < sales_rules.MIN_EXPECTED_WEEKLY:
            continue
        if (week_known[row] == sales_rules.WEEK).sum() < sales_rules.MIN_PAST_WEEKS:
            continue
        count += 1
    return count


def bar(judged: int, target: float) -> float:
    return target / (max(judged, 1) * sales_rules.CHECKS_PER_WEEK * 2)


def judged_by_day(data: ShopData, first_replayed: date, days: int) -> list[int]:
    return [judged_count(data, first_replayed + timedelta(days=offset)) for offset in range(days)]


def print_bar(label: str, judged: list[int]) -> None:
    med = int(np.median(judged))
    print(f"{label}: judged/day min {min(judged)}, median {med}, max {max(judged)}")
    print(f"  bar at {sales_rules.TARGET_FALSE_PER_WEEK:g} false/week: {bar(med, sales_rules.TARGET_FALSE_PER_WEEK):.2e}")


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    original_target = sales_rules.TARGET_FALSE_PER_WEEK
    first_replayed = LAST_DAY - timedelta(days=REPLAY_DAYS - 1)

    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day=LAST_DAY)
        db.flush()
        methods = _methods_before(db, shop.id, first_replayed)
        full = load_shop_data(db, shop.id, LAST_DAY)
        full.methods = [replayable_method(methods.get(key)) for key in full.keys]

        key_index = {key: i for i, key in enumerate(full.keys)}
        planted = db.scalars(select(DemoPlantedProblem).where(DemoPlantedProblem.organization_id == shop.id)).all()
        planted_rows = np.array([key_index[(p.part_id, p.branch_id)] for p in planted if (p.part_id, p.branch_id) in key_index], dtype=int)
        cutoff = (first_replayed - full.first_day).days
        sample = sample_every_third(full.demand[:, :cutoff], planted_rows)
        data = replace(
            full,
            keys=[full.keys[i] for i in sample],
            sold=full.sold[sample],
            demand=full.demand[sample],
            shelf=full.shelf[sample],
            price=full.price[sample],
            cost=full.cost[sample],
        )
        data.methods = [replayable_method(methods.get(key)) for key in data.keys]
        print(f"Sample: {len(sample)} of {len(full.keys)} part-branch pairs.")

        full_judged = judged_by_day(full, first_replayed, REPLAY_DAYS)
        sample_judged = judged_by_day(data, first_replayed, REPLAY_DAYS)
        print_bar("full catalog", full_judged)
        print_bar("1-in-3 sample (what check_alerts actually replays)", sample_judged)

        planted_places = {(p.part_id, p.branch_id) for p in planted}
        spikes_planted = [p for p in planted if p.kind == "sales_spike"]
        drops_planted = [p for p in planted if p.kind == "sales_drop"]

        print("\nOn the sample, with the bar computed each day as for the FULL catalog:")
        print(f"{'target/wk':>10} {'spikes caught':>14} {'drops caught':>14} {'sales false/wk':>15} {'stock false/wk':>15}")
        try:
            for target in TARGETS:
                savepoint = db.begin_nested()
                for offset in range(REPLAY_DAYS):
                    today = first_replayed + timedelta(days=offset)
                    jf, js = full_judged[offset], sample_judged[offset]
                    sales_rules.TARGET_FALSE_PER_WEEK = target * js / jf if jf > 0 else target
                    raise_alerts(db, shop.id, data, today)
                sales_rules.TARGET_FALSE_PER_WEEK = original_target

                alerts = db.scalars(select(Alert).where(Alert.organization_id == shop.id)).all()
                by_key = defaultdict(list)
                for a in alerts:
                    by_key[(a.part_id, a.branch_id, a.kind)].append(a)

                def caught(cases: list[DemoPlantedProblem], kind: str) -> int:
                    return sum(
                        1
                        for p in cases
                        if any(p.first_day <= a.raised_on <= p.last_day + timedelta(days=LATE_DAYS) for a in by_key[(p.part_id, p.branch_id, kind)])
                    )

                spikes_caught = caught(spikes_planted, "sales_spike")
                drops_caught = caught(drops_planted, "sales_drop")
                false_sales = [a for a in alerts if a.kind in SALES_KINDS and (a.part_id, a.branch_id) not in planted_places]
                false_stock = [a for a in alerts if a.kind not in SALES_KINDS and (a.part_id, a.branch_id) not in planted_places]
                weeks = REPLAY_DAYS / 7
                print(
                    f"{target:>10g} {f'{spikes_caught} of {len(spikes_planted)}':>14} {f'{drops_caught} of {len(drops_planted)}':>14} "
                    f"{len(false_sales) / weeks:>15.1f} {len(false_stock) / weeks:>15.1f}"
                )
                savepoint.rollback()
        finally:
            sales_rules.TARGET_FALSE_PER_WEEK = original_target
        db.rollback()
    print(f"\n(took {perf_counter() - started:.0f} s)")


if __name__ == "__main__":
    main()
