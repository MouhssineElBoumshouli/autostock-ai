"""Deterministic, clearly synthetic automotive sales histories for demos and tests."""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

from .forecast import Observation

SYNTHETIC_DATASET_VERSION = "synthetic-automotive-v1"
SYNTHETIC_SEED = 20261009
DEMO_SKUS = {
    "DEMO-BP-001": (12, 5),
    "DEMO-OF-203": (9, 3),
    "DEMO-SP-104": (7, 2),
    "DEMO-AF-331": (8, 2),
    "DEMO-BT-912": (4, 1),
    "DEMO-BR-210": (3, 2),
}


def generate_synthetic_history(
    sku: str,
    end_day: date,
    days: int = 210,
) -> list[Observation]:
    if sku not in DEMO_SKUS:
        raise ValueError("Unknown synthetic demo SKU")
    if days < 1 or days > 730:
        raise ValueError("Synthetic history must contain between 1 and 730 days")

    base, weekend_boost = DEMO_SKUS[sku]
    stable_offset = sum((index + 1) * ord(char) for index, char in enumerate(sku))
    rng = random.Random(SYNTHETIC_SEED + stable_offset)
    first_day = end_day - timedelta(days=days - 1)
    observations = []
    for index in range(days):
        day = first_day + timedelta(days=index)
        weekly = weekend_boost if day.weekday() in (5, 6) else 0
        trend = base * 0.003 * index
        seasonal = math.sin(index * 2 * math.pi / 60) * base * 0.20
        noise = rng.gauss(0, max(1.0, base * 0.23))
        units = max(0, round(base + weekly + trend + seasonal + noise))
        observations.append(Observation(day, float(units)))
    return observations


def iter_synthetic_sales(end_day: date = date(2026, 7, 29), days: int = 210):
    for sku in DEMO_SKUS:
        for observation in generate_synthetic_history(sku, end_day=end_day, days=days):
            yield sku, observation.day, observation.units
