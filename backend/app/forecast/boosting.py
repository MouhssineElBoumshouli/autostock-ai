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


@dataclass
class Prepared:
    """Running sums, so any window's average costs one subtraction."""

    totals: np.ndarray
    counts: np.ndarray
    sale_days: np.ndarray
    first_day: date
    ramadan: np.ndarray  # cumulative Ramadan days, history + MAX_HORIZON

    @property
    def days(self) -> int:
        return self.totals.shape[1] - 1


def prepare(demand: np.ndarray, first_day: date) -> Prepared:
    known = ~np.isnan(demand)

    def running(values: np.ndarray) -> np.ndarray:
        return np.concatenate([np.zeros((values.shape[0], 1)), np.cumsum(values, axis=1)], axis=1)

    days = demand.shape[1]
    return Prepared(
        totals=running(np.where(known, demand, 0.0)),
        counts=running(known.astype(float)),
        sale_days=running((known & (np.nan_to_num(demand) > 0)).astype(float)),
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


def boosting_forecast(data: Prepared, origin: int, horizon: int) -> np.ndarray:
    """Average daily demand expected over [origin, origin + horizon) for every row. NaN when there
    is too little history to learn from."""
    examples, targets = [], []
    for start in range(origin - horizon, FIRST_TRAINING_DAY - 1, -TRAINING_STEP):
        target = window_average(data, start, start + horizon)
        keep = ~np.isnan(target)
        examples.append(features(data, start, horizon)[keep])
        targets.append(target[keep])
    if not examples or sum(len(t) for t in targets) < MIN_EXAMPLES:
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
    model.fit(np.vstack(examples), np.concatenate(targets))
    return model.predict(features(data, origin, horizon))
