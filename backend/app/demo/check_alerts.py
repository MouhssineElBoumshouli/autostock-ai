"""Proof for alerts: replays the demo shop's last 8 weeks day by day, raising alerts exactly as the
daily check does (same rules, daily limit and no-repeat rule), then compares them with the problems
planted on purpose (app/demo/planted_problems.py):
- caught: an alert of the same kind, for the same part and branch, raised between the day the
  problem started and 7 days after it ended; how fast = days from its start to the alert;
- false alarm: an alert on a part and branch where nothing was planted.

The forecast methods are chosen from the sales before the replay only, so no day peeks ahead.
It builds a fresh demo shop (same recipe and seed as app.demo.demo_shop) inside a transaction that
is rolled back at the end, so the real demo shop and its login are never touched.

The full demo shop is ~2,000 parts x 3 branches; replaying 8 weeks day by day for all of them
takes too long for a routine check, so this script samples about 1 in 3 part-branch pairs, keeping
each demand type's share the same as the full catalog (app/demo/sampling.py) — every planted
problem is always kept, so the catch rate is exact; only the false-alarm rate is a sample.

Run inside Docker:  docker compose exec api python -m app.demo.check_alerts
These are results on made-up data, not what a real shop will see.
"""

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import delete, select

from app.alerts.problem import KINDS, NEEDS_ACTION, WORTH_A_LOOK, group_of
from app.alerts.run import DAILY_LIMIT, SALES_DAILY_LIMIT, raise_alerts
from app.alerts.shop_data import load_shop_data, replayable_method
from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.demo.production_guard import refuse_demo_in_production
from app.demo.sampling import SAMPLE_EVERY, sample_every_third
from app.forecast.run import run_forecasts
from app.models import Alert, DemoPlantedProblem, Forecast, SaleLine

LAST_DAY = date(2026, 10, 18)  # fixed, so the result can be checked again
REPLAY_DAYS = 56  # 8 weeks: every planted problem starts inside them
LATE_DAYS = 7  # an alert up to a week after a problem ended still counts as caught


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    first_replayed = LAST_DAY - timedelta(days=REPLAY_DAYS - 1)
    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day=LAST_DAY)
        db.flush()
        methods = _methods_before(db, shop.id, first_replayed)
        full = load_shop_data(db, shop.id, LAST_DAY)
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
        print(f"Sampling 1 in {SAMPLE_EVERY} by demand type (every planted problem kept): {len(sample)} of {len(full.keys)} part-branch pairs.")

        for offset in range(REPLAY_DAYS):
            raise_alerts(db, shop.id, data, first_replayed + timedelta(days=offset))
        alerts = db.scalars(select(Alert).where(Alert.organization_id == shop.id)).all()
        report(planted, alerts, len(data.keys))
        db.rollback()
    print(f"\n(took {perf_counter() - started:.0f} s)")


def _methods_before(db, organization_id, first_replayed: date) -> dict:
    """The 7-day forecast method of every part, chosen from sales before the replay only."""
    savepoint = db.begin_nested()
    db.execute(delete(SaleLine).where(SaleLine.organization_id == organization_id, SaleLine.sold_on >= first_replayed))
    run_forecasts(db, organization_id, "manual")
    methods = {
        (part, branch): method
        for part, branch, method in db.execute(
            select(Forecast.part_id, Forecast.branch_id, Forecast.method).where(
                Forecast.organization_id == organization_id, Forecast.horizon_days == 7
            )
        )
    }
    savepoint.rollback()
    return methods


def report(planted: list[DemoPlantedProblem], alerts: list[Alert], series: int) -> None:
    by_key = defaultdict(list)
    for alert in alerts:
        by_key[(alert.part_id, alert.branch_id, alert.kind)].append(alert)
    planted_places = {(p.part_id, p.branch_id) for p in planted}

    print(f"Replayed {REPLAY_DAYS} days to {LAST_DAY} on {series} parts x branches: {len(alerts)} alerts raised.\n")
    print(f"{'Planted problem':<16}{'planted':>8}{'caught':>8}{'missed':>8}   days to catch (median, range)")
    for kind in KINDS:
        cases = [p for p in planted if p.kind == kind]
        delays = []
        for p in cases:
            hits = [a for a in by_key[(p.part_id, p.branch_id, kind)] if p.first_day <= a.raised_on <= p.last_day + timedelta(days=LATE_DAYS)]
            if hits:
                delays.append(min((a.raised_on - p.first_day).days for a in hits))
        speed = f"{np.median(delays):.0f} ({min(delays)} to {max(delays)})" if delays else "-"
        print(f"{kind:<16}{len(cases):>8}{len(delays):>8}{len(cases) - len(delays):>8}   {speed}")

    false = [a for a in alerts if (a.part_id, a.branch_id) not in planted_places]
    weeks = REPLAY_DAYS / 7
    kinds = ", ".join(f"{kind} {count}" for kind, count in Counter(a.kind for a in false).most_common())
    print(f"\nFalse alarms (nothing planted there): {len(false)} in {weeks:.0f} weeks = {len(false) / weeks:.1f} a week ({kinds or 'none'}).")
    for group, label in ((NEEDS_ACTION, "Needs action"), (WORTH_A_LOOK, "Worth a look")):
        in_group = [a for a in alerts if group_of(a.kind) == group]
        wrong = sum(1 for a in false if group_of(a.kind) == group)
        real_pct = 100 * (len(in_group) - wrong) / len(in_group) if in_group else 0
        print(f"  {label}: {len(in_group)} alerts ({len(in_group) / REPLAY_DAYS:.1f}/day), {wrong} of them false alarms ({real_pct:.0f}% real).")
    per_day = Counter(a.raised_on for a in alerts)
    sales_per_day = Counter(a.raised_on for a in alerts if group_of(a.kind) == WORTH_A_LOOK)
    print(f"Days the daily limit of {DAILY_LIMIT} was reached: {sum(1 for n in per_day.values() if n >= DAILY_LIMIT)} of {REPLAY_DAYS}.")
    print(f"Days the sales limit of {SALES_DAILY_LIMIT} was reached: {sum(1 for n in sales_per_day.values() if n >= SALES_DAILY_LIMIT)} of {REPLAY_DAYS}.")


if __name__ == "__main__":
    main()
