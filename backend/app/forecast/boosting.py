"""One gradient boosting model (scikit-learn) learned across all parts at once, so a part with a
short history can learn from the others: summer peaks, Ramadan, slow months.

For a horizon of h days it predicts the average daily demand over the next h days from simple
facts known at that moment: recent averages, the same weeks last year, the season and Ramadan.
It learns only from windows that ended before the forecast day, in time order (never shuffled).
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.forecast.calendar import ramadan_flags

FIRST_TRAINING_DAY = 91  # every example has at least 13 weeks of history before it
TRAINING_STEP = 7  # one example per part per week
MIN_EXAMPLES = 200
MAX_HORIZON = 60
ROWS_AT_A_TIME = 5000


@dataclass
class Prepared:
    """Running sums, so any window's average costs one subtraction. Demand is whole pieces, so the
    sums are whole numbers, kept as small integers (a quarter to half the memory of decimals; any
    division turns them back into decimals first, so every result is the same)."""

    totals: np.ndarray  # pieces
    counts: np.ndarray  # known days
    sale_days: np.ndarray  # known days with a sale
    first_day: date
    ramadan: np.ndarray  # cumulative Ramadan days, history + MAX_HORIZON

    @property
    def days(self) -> int:
        return self.totals.shape[1] - 1


def prepare(demand: np.ndarray, first_day: date) -> Prepared:
    """`demand`: whole pieces per row per day, NaN where unknown."""
    rows, days = demand.shape
    totals = np.zeros((rows, days + 1), dtype=np.int32)
    counts = np.zeros((rows, days + 1), dtype=np.int16)
    sale_days = np.zeros((rows, days + 1), dtype=np.int16)
    for start in range(0, rows, ROWS_AT_A_TIME):  # a few thousand rows at a time: no full-size temporary tables
        part = demand[start : start + ROWS_AT_A_TIME]
        known = ~np.isnan(part)
        totals[start : start + ROWS_AT_A_TIME, 1:] = np.cumsum(np.where(known, part, 0).astype(np.int64), axis=1)
        counts[start : start + ROWS_AT_A_TIME, 1:] = np.cumsum(known, axis=1)
        sale_days[start : start + ROWS_AT_A_TIME, 1:] = np.cumsum(known & (np.nan_to_num(part) > 0), axis=1)
    return Prepared(
        totals=totals,
        counts=counts,
        sale_days=sale_days,
        first_day=first_day,
        ramadan=np.concatenate([[0.0], np.cumsum(ramadan_flags(first_day, days + MAX_HORIZON))]),
    )


def window_average(data: Prepared, start: int, end: int) -> np.ndarray:
    """Average daily demand over known days in [start, end). NaN if none are known or out of range."""
    start, end = max(start, 0), min(end, data.days)
    if start >= end:
        return np.full(data.totals.shape[0], np.nan)
    count = data.counts[:, end] - data.counts[:, start]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, (data.totals[:, end] - data.totals[:, start]) / count, np.nan)


def features(data: Prepared, origin: int, horizon: int) -> np.ndarray:
    rows = data.totals.shape[0]
    count_91 = data.counts[:, origin] - data.counts[:, max(origin - 91, 0)]
    with np.errstate(invalid="ignore", divide="ignore"):
        sale_share = np.where(count_91 > 0, (data.sale_days[:, origin] - data.sale_days[:, max(origin - 91, 0)]) / count_91, np.nan)
    middle = data.first_day + timedelta(days=origin + horizon // 2)
    angle = 2 * np.pi * middle.timetuple().tm_yday / 365.25
    ramadan_ahead = (data.ramadan[origin + horizon] - data.ramadan[origin]) / horizon
    ramadan_before = (data.ramadan[origin] - data.ramadan[max(origin - 28, 0)]) / 28
    columns = [
        window_average(data, origin - 7, origin),
        window_average(data, origin - 28, origin),
        window_average(data, origin - 91, origin),
        window_average(data, origin - 365, origin),
        sale_share,
        window_average(data, origin - 364, origin - 364 + horizon),  # the same weeks last year
        window_average(data, origin - 364 - 28, origin - 364),  # the 4 weeks before them
        *(np.full(rows, value) for value in (np.sin(angle), np.cos(angle), ramadan_ahead, ramadan_before)),
    ]
    return np.column_stack(columns)


FEATURES = 11  # the columns features() returns


def boosting_forecasts(data: Prepared, origins: list[int], horizon: int) -> np.ndarray:
    """Average daily demand expected over [origin, origin + horizon) for every row, one column per
    origin. NaN when there is too little history to learn from.

    A forecast from `origin` learns from the windows starting at origin - horizon, then every
    TRAINING_STEP days before that, newest first. Origins a whole number of weeks apart share most
    of those windows, so each window's examples are built once, and an older origin learns from
    the tail of a newer one's examples: the same windows in the same order, so the same model."""
    forecasts: dict[int, np.ndarray] = {}
    for origin in sorted(origins, reverse=True):
        if origin in forecasts:
            continue
        newest = origin - horizon
        examples, targets, first_row = _training_examples(data, newest, horizon)
        for other in origins:
            start = other - horizon
            if other not in forecasts and start <= newest and (newest - start) % TRAINING_STEP == 0:
                begin = first_row.get(start, len(targets))  # no windows at all before an origin this early
                forecasts[other] = _learn_and_forecast(examples[begin:], targets[begin:], data, other, horizon)
    return np.column_stack([forecasts[origin] for origin in origins])


def _training_examples(data: Prepared, newest: int, horizon: int) -> tuple[np.ndarray, np.ndarray, dict[int, int]]:
    """Features and real average demand of every window from `newest` back, newest first, and the
    row where each window's examples begin. Written into one array of the right size (for a big
    shop it holds millions of examples: no second copy is made)."""
    starts = list(range(newest, FIRST_TRAINING_DAY - 1, -TRAINING_STEP))
    targets = [window_average(data, start, start + horizon) for start in starts]
    keep = [~np.isnan(target) for target in targets]
    sizes = [int(k.sum()) for k in keep]
    first_row = dict(zip(starts, np.cumsum([0, *sizes[:-1]]).tolist()))
    examples = np.empty((sum(sizes), FEATURES))
    for start, kept, size in zip(starts, keep, sizes):
        examples[first_row[start] : first_row[start] + size] = features(data, start, horizon)[kept]
    target_rows = np.concatenate([target[kept] for target, kept in zip(targets, keep)]) if starts else np.empty(0)
    return examples, target_rows, first_row


def _learn_and_forecast(examples: np.ndarray, targets: np.ndarray, data: Prepared, origin: int, horizon: int) -> np.ndarray:
    if len(targets) < MIN_EXAMPLES:
        return np.full(data.totals.shape[0], np.nan)
    model = HistGradientBoostingRegressor(
        loss="poisson",  # demand is a count: never negative, often small
        learning_rate=0.05,
        max_iter=150,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        early_stopping=False,  # early stopping would pick a random (shuffled) validation set
        random_state=0,
    )
    model.fit(examples, targets)
    return model.predict(features(data, origin, horizon))
