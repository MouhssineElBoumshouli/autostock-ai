"""Sales spike / drop: the last 7 days of real sales fall outside the range the forecast would have
given for them, for that part in that branch.

The range is made the same way as the forecast's (the method's own past misses, widened per demand
type until it catches the truth often enough), as it stood the day before the week began, so it
never peeks at the week it judges. The forecast's 80% range is wrong 1 week in 5 by design, which
would flood the shop with alerts; here each side is widened until past weeks fell outside it at
most MISS_SHARE of the time.
"""

import numpy as np

from app.alerts.problem import Problem, day_label, money
from app.alerts.shop_data import ShopData
from app.forecast.backtest import range_gaps, side_widen_factors
from app.forecast.demand_types import demand_type

WEEK = 7
PAST_WEEKS = 12  # past weeks the range learns from
MIN_PAST_WEEKS = 8
# Per side: 1 past week in 200 above the range, 1 in 200 below. Chosen on a second demo shop
# (seed 8: 0.01 gave 9.6 false alarms a week, 0.005 gave 5.9, 0.0025 gave 3.9 but caught fewer
# drops), then measured on the usual one (seed 7) in docs/journey.md, so the result isn't tuned to it.
MISS_SHARE = 0.005
# Parts expected to sell fewer than 5 a week are not judged: for them a week of 0, or double the
# usual, is ordinary chance (with 2 expected, a week of 0 happens 1 time in 7).
MIN_EXPECTED_WEEKLY = 5.0
MIN_KNOWN_DAYS_FOR_SPIKE = 4  # a spike can be seen in a part-week; a drop needs all 7 days on the shelf


def sales_problems(data: ShopData, end: int) -> list[Problem]:
    """Spikes and drops for the week ending on day index `end`."""
    start = end - WEEK + 1
    origins = [start - WEEK * k for k in range(PAST_WEEKS, 0, -1) if start - WEEK * k >= 0]
    if len(origins) < MIN_PAST_WEEKS:
        return []
    known = ~np.isnan(data.demand)
    filled = np.where(known, data.demand, 0.0)
    week_known = np.column_stack([known[:, o : o + WEEK].sum(axis=1) for o in [*origins, start]])
    week_sold = np.column_stack([filled[:, o : o + WEEK].sum(axis=1) for o in [*origins, start]])
    with np.errstate(invalid="ignore", divide="ignore"):
        week_rate = np.where(week_known > 0, week_sold / week_known, np.nan)  # daily rate in each week

    candidates = []  # (row, demand type, expected, predicted past rates, actual past rates)
    for row, method in enumerate(data.methods):
        expected = float(data.forecast_table(method)[row, start]) * WEEK
        if expected < MIN_EXPECTED_WEEKLY:
            continue
        usable = ~np.isnan(week_rate[row, :-1])
        if usable.sum() < MIN_PAST_WEEKS:
            continue
        predicted = data.forecast_table(method)[row, origins][usable]
        candidates.append((row, demand_type(data.demand[row, :start]), expected, predicted, week_rate[row, :-1][usable]))

    widen = {
        kind: side_widen_factors([(p, a) for _, k, _, p, a in candidates if k == kind], WEEK, MISS_SHARE)
        for kind in {c[1] for c in candidates}
    }
    problems = []
    for row, kind, expected, predicted, actual in candidates:
        below, above = range_gaps(expected, predicted, actual, WEEK)
        low, high = max(expected - widen[kind][0] * below, 0.0), expected + widen[kind][1] * above
        days_known = int(week_known[row, -1])
        sold = int(data.sold[row, start : end + 1].sum())
        if sold > high and days_known >= MIN_KNOWN_DAYS_FOR_SPIKE:
            problems.append(_problem(data, row, "sales_spike", start, end, sold, expected, low, high))
        elif sold < low and days_known == WEEK:
            problems.append(_problem(data, row, "sales_drop", start, end, sold, expected, low, high))
    return problems


def _problem(data: ShopData, row: int, kind: str, start: int, end: int, sold: int, expected: float, low: float, high: float) -> Problem:
    at_stake = round(abs(sold - expected)) * data.money_per_piece(row, sales=True)
    usual_low, usual_high = int(np.floor(low)), int(np.ceil(high))
    side = "above" if kind == "sales_spike" else "below"
    sentence = (
        f"Sold {sold} in the 7 days to {day_label(data.day(end))}, usually {usual_low} to {usual_high}. "
        f"About {money(at_stake, data.currency)} of sales {side} usual."
    )
    numbers = {"sold": sold, "usual_low": usual_low, "usual_high": usual_high, "expected": round(expected, 1), "week_end": data.day(end).isoformat()}
    return Problem(*data.keys[row], kind, data.day(start), at_stake, sentence, numbers)
