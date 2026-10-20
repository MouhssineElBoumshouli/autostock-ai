"""Sales spike / drop: the last 7 days of real sales are far from what the forecast expected for
that part in that branch, judged with a count model (see counts.py).

- Expected: the forecast method's own number for the week, as it stood the day before the week
  began, so it never peeks at the week it judges.
- Spread: how far the part's sales usually land from that forecast, from its past 26 weeks
  (negative binomial; Poisson when it sells evenly). 26 counts give a steadier spread than reading
  a rare tail straight off a few past weeks.
- How rare is rare enough: set from a target of TARGET_FALSE_PER_WEEK false alarms for the whole
  shop. Every judged part is checked every day on a rolling week (7 checks a week) in both
  directions, so each check may be wrong at most target / (judged parts x 7 x 2) of the time.
- And a real change: at least 50% above or below what was expected, and at least 5 pieces.
"""

import numpy as np

from app.alerts.counts import chance_at_least, chance_at_most, spread
from app.alerts.problem import Problem, day_label, money
from app.alerts.shop_data import ShopData

WEEK = 7
PAST_WEEKS = 26  # past weeks the spread is learned from
MIN_PAST_WEEKS = 8
# Chosen with the owner as "about 2 a week for the whole shop" (Step 6a review).
TARGET_FALSE_PER_WEEK = 2.0
CHECKS_PER_WEEK = 7  # the rolling week is judged every day
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

    judged = []  # (row, expected this week, the part's extra spread)
    for row, method in enumerate(data.methods):
        table = data.forecast_table(method)
        expected = float(table[row, start]) * WEEK
        full_weeks = week_known[row, :-1] == WEEK  # past weeks with every day on the shelf
        if expected < MIN_EXPECTED_WEEKLY or full_weeks.sum() < MIN_PAST_WEEKS:
            continue
        predicted = table[row, origins][full_weeks] * WEEK
        judged.append((row, expected, spread(predicted, week_sold[row, :-1][full_weeks])))

    rare = TARGET_FALSE_PER_WEEK / (max(len(judged), 1) * CHECKS_PER_WEEK * 2)
    problems = []
    for row, expected, extra_spread in judged:
        days_known = int(week_known[row, -1])
        sold = int(data.sold[row, start : end + 1].sum())
        if (
            days_known >= MIN_KNOWN_DAYS_FOR_SPIKE
            and sold >= (1 + MIN_CHANGE) * expected
            and sold - expected >= MIN_PIECES
            and chance_at_least(sold, expected * days_known / WEEK, extra_spread) <= rare
        ):
            problems.append(_problem(data, row, "sales_spike", start, end, sold, expected, extra_spread))
        elif (
            days_known == WEEK
            and sold <= (1 - MIN_CHANGE) * expected
            and expected - sold >= MIN_PIECES
            and chance_at_most(sold, expected, extra_spread) <= rare
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
    side = "above" if kind == "sales_spike" else "below"
    sentence = (
        f"Sold {sold} in the 7 days to {day_label(data.day(end))}, usually {usual_low} to {usual_high}. "
        f"About {money(at_stake, data.currency)} of sales {side} usual."
    )
    numbers = {"sold": sold, "usual_low": usual_low, "usual_high": usual_high, "expected": round(expected, 1), "week_end": data.day(end).isoformat()}
    return Problem(*data.keys[row], kind, data.day(start), at_stake, sentence, numbers)
