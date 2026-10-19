"""Simple forecasting methods, all in plain numpy.

Each takes the demand table (rows = part in a branch, columns = days, NaN = unknown) and returns a
table with one more column: column `t` is the daily demand the method expects from day `t` on,
using only days before `t`. So the same table serves the backtest (any past day) and the real
forecast (the last column). Unknown days are skipped, never treated as zero.
"""

import numpy as np

SMOOTHING = 0.1  # how fast the methods below follow new sales (standard value for daily data)


def rolling_average(demand: np.ndarray, days: int) -> np.ndarray:
    """Average of the known days among the last `days` days. NaN when none are known."""
    known = ~np.isnan(demand)
    totals = _running_sum(np.where(known, demand, 0.0))
    counts = _running_sum(known.astype(float))
    ends = np.arange(demand.shape[1] + 1)
    starts = np.maximum(ends - days, 0)
    total = totals[:, ends] - totals[:, starts]
    count = counts[:, ends] - counts[:, starts]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def four_week_average(demand: np.ndarray) -> np.ndarray:
    """The baseline. If the last 4 weeks are all unknown, the last 13 weeks, else 0."""
    return _first_known(rolling_average(demand, 28), rolling_average(demand, 91))


def last_week(demand: np.ndarray) -> np.ndarray:
    """Same weekday last week, repeated: over a 7/30/60-day total that is last week's daily average."""
    return _first_known(rolling_average(demand, 7), four_week_average(demand))


def exponential_smoothing(demand: np.ndarray, alpha: float = SMOOTHING) -> np.ndarray:
    rows, days = demand.shape
    forecasts = np.zeros((rows, days + 1))
    level = np.full(rows, np.nan)
    for t in range(days):
        forecasts[:, t] = level
        sold = demand[:, t]
        known = ~np.isnan(sold)
        starting = known & np.isnan(level)
        level = np.where(starting, sold, level)
        level = np.where(known & ~starting, level + alpha * (sold - level), level)
    forecasts[:, days] = level
    return np.nan_to_num(forecasts)


def croston(demand: np.ndarray, alpha: float = SMOOTHING, correction: float = 1.0) -> np.ndarray:
    """For slow sellers: smooths the size of a sale and the number of days between sales separately.
    Daily demand = size / days between. Until a second sale shows a real gap, the gap so far is used."""
    rows, days = demand.shape
    forecasts = np.zeros((rows, days + 1))
    size = np.full(rows, np.nan)
    gap = np.full(rows, np.nan)
    days_since = np.zeros(rows)  # known days since the last sale
    for t in range(days + 1):
        with np.errstate(invalid="ignore", divide="ignore"):
            gap_now = np.where(np.isnan(gap), np.maximum(days_since, 1), gap)
            forecasts[:, t] = np.where(np.isnan(size), 0.0, correction * size / gap_now)
        if t == days:
            break
        sold = demand[:, t]
        known = ~np.isnan(sold)
        days_since += known
        sale = known & (sold > 0)
        first = sale & np.isnan(size)
        second = sale & ~first & np.isnan(gap)
        later = sale & ~first & ~second
        size = np.where(first, sold, np.where(sale & ~first, size + alpha * (sold - size), size))
        gap = np.where(second, days_since, np.where(later, gap + alpha * (days_since - gap), gap))
        days_since = np.where(sale, 0, days_since)
    return forecasts


def sba(demand: np.ndarray, alpha: float = SMOOTHING) -> np.ndarray:
    """Croston with the Syntetos-Boylan correction: plain Croston forecasts a little too high."""
    return croston(demand, alpha, correction=1 - alpha / 2)


def tsb(demand: np.ndarray, alpha: float = SMOOTHING, beta: float = SMOOTHING) -> np.ndarray:
    """Teunter-Syntetos-Babai: smooths the chance of a sale each day, so a part that stopped selling
    fades toward zero (Croston never lowers its forecast between sales)."""
    rows, days = demand.shape
    forecasts = np.zeros((rows, days + 1))
    chance = np.zeros(rows)
    size = np.full(rows, np.nan)
    for t in range(days + 1):
        forecasts[:, t] = np.where(np.isnan(size), 0.0, chance * size)
        if t == days:
            break
        sold = demand[:, t]
        known = ~np.isnan(sold)
        sale = known & (sold > 0)
        chance = np.where(known, chance + beta * (sale - chance), chance)
        size = np.where(sale & np.isnan(size), sold, np.where(sale, size + alpha * (sold - size), size))
    return forecasts


def _running_sum(values: np.ndarray) -> np.ndarray:
    return np.concatenate([np.zeros((values.shape[0], 1)), np.cumsum(values, axis=1)], axis=1)


def _first_known(*choices: np.ndarray) -> np.ndarray:
    result = choices[0]
    for choice in choices[1:]:
        result = np.where(np.isnan(result), choice, result)
    return np.nan_to_num(result)
