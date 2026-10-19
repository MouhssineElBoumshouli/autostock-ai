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


def choose(scores: dict[str, Score | None], baseline: str, windows: int) -> tuple[str, str]:
    """The method to use and why. The baseline unless another method clearly beat it on this part's past."""
    if windows < MIN_WINDOWS:
        return baseline, f"Too little history to test ({windows} of {MIN_WINDOWS} past windows): using the 4-week average."
    base = scores[baseline]
    others = {name: s for name, s in scores.items() if name != baseline and s is not None}
    if not others:
        return baseline, "No other method could be tested: using the 4-week average."
    name = min(others, key=lambda n: others[n].error)
    if base.error > 0 and others[name].error < (1 - MARGIN) * base.error:
        gain = round(100 * (1 - others[name].error / base.error))
        return name, f"Beat the 4-week average by {gain}% on this part's past {windows} windows."
    return baseline, f"No method beat the 4-week average by at least {round(MARGIN * 100)}% on this part's past."


def forecast_range(quantity: float, predicted: np.ndarray, actual: np.ndarray, horizon: int) -> tuple[float, float]:
    """Low and high: the forecast plus the 10th and 90th percentile of its own past misses.

    Past windows overlap and are few, so they can look calmer than reality. The range is therefore
    never narrower than chance alone allows for counted sales (Poisson: 1.28 x square root).
    """
    misses = (actual - predicted) * horizon
    if len(misses) < MIN_WINDOWS or np.isnan(misses).any():
        return 0.0, max(2 * quantity, 1.0)  # nothing to learn from: a wide, honest range
    chance = 1.28 * np.sqrt(quantity)
    low = quantity + min(float(np.quantile(misses, 0.1)), -chance)
    high = quantity + max(float(np.quantile(misses, 0.9)), chance)
    return max(low, 0.0), high
