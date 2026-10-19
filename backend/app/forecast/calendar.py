"""Moroccan calendar facts the forecasts and the demo shop both use."""

from datetime import date, timedelta

import numpy as np

# First day of Ramadan in Morocco (moon sighting can move it by one day). It lasts about 30 days.
RAMADAN_FIRST_DAYS = [date(2024, 3, 12), date(2025, 3, 2), date(2026, 2, 19), date(2027, 2, 9), date(2028, 1, 29)]
RAMADAN_DAYS = 30


def is_ramadan(day: date) -> bool:
    return any(first <= day < first + timedelta(days=RAMADAN_DAYS) for first in RAMADAN_FIRST_DAYS)


def ramadan_flags(first_day: date, days: int) -> np.ndarray:
    """1.0 for each Ramadan day in the `days` days starting at `first_day`, else 0.0."""
    return np.array([is_ramadan(first_day + timedelta(days=i)) for i in range(days)], dtype=float)
