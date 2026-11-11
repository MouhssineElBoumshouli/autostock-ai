"""Honest measurement: pretend we are back in the past, forecast, and compare with what really sold.

Windows go in time order only. A method may only use days before each window. Scores:
- WAPE: total pieces we were off by, divided by total pieces sold. 0.30 = off by 30%.
- MASE: average error divided by the part's usual day-to-day change. Below 1 = better than that.
(MAPE is not used: it breaks on days with zero sales, which most parts have.)
"""

from dataclasses import dataclass

import numpy as np

from app.forecast.boosting import FIRST_TRAINING_DAY, Prepared, window_average

WINDOWS = 12  # past windows tested per part
STEP = 7  # one week between two windows
MIN_KNOWN_BEFORE = 28  # a window counts only if the part had 4 known weeks before it
MIN_WINDOWS = 3
MARGIN = 0.05  # a method must beat the baseline by at least 5%, so luck alone rarely wins
TARGET_COVERAGE = 0.8  # ranges should catch the real total 8 times out of 10
CHECK_WINDOWS = 4  # newest windows used to check the ranges
WIDEN_STEPS = np.round(np.arange(1.0, 5.01, 0.05), 2)


@dataclass
class Score:
    error: float  # total pieces off, over all tested windows
    wape: float | None
    mase: float | None


def backtest_origins(days: int, horizon: int) -> list[int]:
    """First day of each past window, oldest first. Each window ends before the history does."""
    origins = [days - horizon - STEP * k for k in range(WINDOWS)]
    return sorted(o for o in origins if o >= FIRST_TRAINING_DAY)


def actuals(data: Prepared, origins: list[int], horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each row and window: real average daily demand, known days, and whether the window counts."""
    if not origins:
        empty = np.zeros((data.totals.shape[0], 0))
        return empty, empty, empty.astype(bool)
    rates = np.column_stack([window_average(data, o, o + horizon) for o in origins])
    known = np.column_stack([data.counts[:, o + horizon] - data.counts[:, o] for o in origins])
    before = np.column_stack([data.counts[:, o] for o in origins])
    return rates, known, (known > 0) & (before >= MIN_KNOWN_BEFORE)


def mase_scale(history: np.ndarray) -> float:
    """Average change from one day to the next, over pairs of known days."""
    changes = np.abs(np.diff(history))
    changes = changes[~np.isnan(changes)]
    return float(changes.mean()) if len(changes) else 0.0


def score(predicted: np.ndarray, actual: np.ndarray, known: np.ndarray, scale: float) -> Score | None:
    """None when the method had no forecast for one of the windows."""
    if len(predicted) == 0 or np.isnan(predicted).any():
        return None
    misses = np.abs(predicted - actual)
    sold = float((actual * known).sum())
    error = float((misses * known).sum())
    return Score(
        error=error,
        wape=error / sold if sold > 0 else None,
        mase=float(misses.mean()) / scale if scale > 0 else None,
    )


def choose_for_type(errors: dict[str, float], baseline: str, kind: str, parts: int) -> tuple[str, str]:
    """One method for all parts of a demand type, from their pooled past errors (pieces off).
    The baseline unless another method beat it by at least MARGIN."""
    others = {name: error for name, error in errors.items() if name != baseline}
    if parts == 0 or not others:
        return baseline, f"Not enough {kind} parts with history to compare methods: using the 4-week average."
    name = min(others, key=others.get)
    base = errors[baseline]
    if base > 0 and others[name] < (1 - MARGIN) * base:
        gain = round(100 * (1 - others[name] / base))
        return name, f"For {kind} parts, it beat the 4-week average by {gain}% over the past of {parts} parts."
    return baseline, f"For {kind} parts, no method beat the 4-week average by at least {round(MARGIN * 100)}%."


def range_gaps(quantity: float, predicted: np.ndarray, actual: np.ndarray, horizon: int) -> tuple[float, float]:
    """How far below and above the forecast the range goes: the 10th and 90th percentile of the
    method's own past misses.

    Never narrower than chance alone allows for counted sales (Poisson: 1.28 x square root).
    """
    below, above = range_gaps_of_rows(np.array([quantity]), predicted[None, :], actual[None, :], horizon)
    return float(below[0]), float(above[0])


def range_gaps_of_rows(quantities: np.ndarray, predicted: np.ndarray, actual: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """range_gaps for many forecasts at once: one row of past windows per forecast."""
    nothing_to_learn = (quantities, np.where(1.0 > quantities, 1.0, quantities))  # a wide range (0 to double)
    misses = (actual - predicted) * horizon
    if misses.shape[1] < MIN_WINDOWS:
        return nothing_to_learn
    unknown = np.isnan(misses).any(axis=1)
    chance = 1.28 * np.sqrt(quantities)
    low, high = -np.quantile(misses, 0.1, axis=1), np.quantile(misses, 0.9, axis=1)
    below = np.where(chance > low, chance, low)  # the bigger one, the past misses' unless chance is bigger
    above = np.where(chance > high, chance, high)
    return np.where(unknown, nothing_to_learn[0], below), np.where(unknown, nothing_to_learn[1], above)


def forecast_range(quantity: float, below: float, above: float, widen: float = 1.0) -> tuple[float, float]:
    return max(quantity - widen * below, 0.0), quantity + widen * above


def widen_factor(cases: list[tuple[np.ndarray, np.ndarray]], horizon: int) -> float:
    """How much to widen the ranges of one demand type so they catch the real total TARGET_COVERAGE
    of the time. Tested honestly in time order: ranges built from older windows, checked on the
    newest CHECK_WINDOWS. `cases` = each part's (predicted, actual) daily rates per past window."""
    forecasts, reals, belows, aboves = [], [], [], []
    long_enough = [case for case in cases if len(case[1]) >= MIN_WINDOWS + CHECK_WINDOWS]
    for windows in sorted({len(actual) for _, actual in long_enough}):  # cases with as many windows, all at once
        predicted = np.array([p for p, a in long_enough if len(a) == windows])
        actual = np.array([a for _, a in long_enough if len(a) == windows])
        learn = slice(None, -CHECK_WINDOWS)
        for window in range(windows - CHECK_WINDOWS, windows):
            below, above = range_gaps_of_rows(predicted[:, window] * horizon, predicted[:, learn], actual[:, learn], horizon)
            forecasts.append(predicted[:, window] * horizon)
            reals.append(actual[:, window] * horizon)
            belows.append(below)
            aboves.append(above)
    if not forecasts:
        return 1.0
    forecasts, reals, belows, aboves = map(np.concatenate, (forecasts, reals, belows, aboves))
    for widen in WIDEN_STEPS:
        caught = (reals >= forecasts - widen * belows) & (reals <= forecasts + widen * aboves)
        if caught.mean() >= TARGET_COVERAGE:
            return float(widen)
    return float(WIDEN_STEPS[-1])
