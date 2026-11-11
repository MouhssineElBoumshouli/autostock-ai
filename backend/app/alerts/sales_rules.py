"""Sales spike / drop: the last 7 days of real sales are far from what the forecast expected for
that part in that branch, judged with a count model (see counts.py).

- Expected: the forecast method's own number for the week, as it stood the day before the week
  began, so it never peeks at the week it judges.
- Spread: how far the part's sales usually land from that forecast, from its past 26 weeks
  (negative binomial; Poisson when it sells evenly). 26 counts give a steadier spread than reading
  a rare tail straight off a few past weeks.
- How rare is rare enough: PER_PART_BAR, fixed. Up to step 8c-1 this was a shop-wide weekly budget
  split across every judged part, so a bigger shop meant a stricter bar per part and, with a
  ~2,000-part catalog, almost no sales alerts at all — the catalog size, not the demand, decided
  whether a real spike or drop got caught. A fixed per-part bar judges every shop the same way; a
  bigger shop naturally sees more sales alerts, capped for the owner by SALES_DAILY_LIMIT
  (app/alerts/run.py), which keeps only the ones worth the most money.
- And a real change: at least 50% above or below what was expected, and at least 5 pieces.
"""

import numpy as np

from app.alerts.counts import chance_at_least, chance_at_most, spread
from app.alerts.problem import Problem, day_label
from app.alerts.shop_data import ShopData

WEEK = 7
PAST_WEEKS = 26  # past weeks the spread is learned from
MIN_PAST_WEEKS = 8
# How rare a week must be, for one part checked one way (spike or drop) on one day, to be a real
# problem rather than ordinary chance. Fixed per part: a bigger catalog is judged exactly as
# strictly as a small one, not more leniently. Chosen on the second demo shop (seed 8), never the
# main one (step 6a's own rule): tried 2e-5 to 5e-3; catches peak and flatten at 1e-3 (11 of 15
# spikes, 8 of 15 drops) and going looser only adds false alarms that start crowding real ones out
# of the daily cap (5e-3: still 11/15 spikes but drops fall back to 5/15).
PER_PART_BAR = 1e-3
MIN_CHANGE = 0.5  # +50% for a spike, -50% for a drop
MIN_PIECES = 5
# Parts expected to sell fewer than 8 a week are not judged: for them a week of 0, or double the
# usual, is ordinary chance (with 2 expected, a week of 0 happens 1 time in 7). 8 rather than 5 was
# chosen on the second demo shop (seed 8): 1.9 false alarms a week instead of 2.5, same catches.
MIN_EXPECTED_WEEKLY = 8.0
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

    columns = [*origins, start]
    tables = {method: data.forecasts_from(method, columns) for method in set(data.methods)}
    problems = []
    for row, method in enumerate(data.methods):
        table = tables[method]
        expected = float(table[row, -1]) * WEEK
        full_weeks = week_known[row, :-1] == WEEK  # past weeks with every day on the shelf
        if expected < MIN_EXPECTED_WEEKLY or full_weeks.sum() < MIN_PAST_WEEKS:
            continue
        predicted = table[row, :-1][full_weeks] * WEEK
        extra_spread = spread(predicted, week_sold[row, :-1][full_weeks])

        days_known = int(week_known[row, -1])
        sold = int(data.sold[row, start : end + 1].sum())
        if (
            days_known >= MIN_KNOWN_DAYS_FOR_SPIKE
            and sold >= (1 + MIN_CHANGE) * expected
            and sold - expected >= MIN_PIECES
            and chance_at_least(sold, expected * days_known / WEEK, extra_spread) <= PER_PART_BAR
        ):
            problems.append(_problem(data, row, "sales_spike", start, end, sold, expected, extra_spread))
        elif (
            days_known == WEEK
            and sold <= (1 - MIN_CHANGE) * expected
            and expected - sold >= MIN_PIECES
            and chance_at_most(sold, expected, extra_spread) <= PER_PART_BAR
        ):
            problems.append(_problem(data, row, "sales_drop", start, end, sold, expected, extra_spread))
    return problems


def usual_range(expected: float, extra_spread: float) -> tuple[int, int]:
    """What a normal week looks like for the sentence: the middle 80% of the count model."""
    low = 0
    while chance_at_most(low, expected, extra_spread) < 0.1:
        low += 1
    high = low
    while chance_at_most(high, expected, extra_spread) < 0.9:
        high += 1
    return low, high


def _problem(data: ShopData, row: int, kind: str, start: int, end: int, sold: int, expected: float, extra_spread: float) -> Problem:
    at_stake = round(abs(sold - expected)) * data.money_per_piece(row, sales=True)
    usual_low, usual_high = usual_range(expected, extra_spread)
    sentence = f"Sold {sold} in the 7 days to {day_label(data.day(end))}, usually {usual_low} to {usual_high}."
    numbers = {"sold": sold, "usual_low": usual_low, "usual_high": usual_high, "expected": round(expected, 1), "week_end": data.day(end).isoformat()}
    return Problem(*data.keys[row], kind, data.day(start), at_stake, sentence, numbers)
