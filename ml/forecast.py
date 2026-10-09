"""Evaluate demand forecasting without leaking future observations.

Input: daily quantities for ONE product, containing ISO dates and nonnegative sales.
Missing calendar dates between first and last observation are treated as zero.
Products with insufficient history never get a numeric demand prediction.

The ML model is intentionally NOT Odoo-integrated in this foundation release.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import cos, pi, sin
from statistics import mean
from typing import Iterable

import numpy as np
from sklearn.ensemble import RandomForestRegressor

MIN_HISTORY = 90
MIN_TRAIN_EXAMPLES = 30
SEED = 42


@dataclass(frozen=True)
class Observation:
    day: date
    units: float


@dataclass(frozen=True)
class Prediction:
    day: str
    units: float
    lower_heuristic: float
    upper_heuristic: float


@dataclass(frozen=True)
class ForecastResult:
    status: str
    selected_method: str | None
    history_days: int
    evaluation_days: int
    baseline_mae: float | None
    ml_mae: float | None
    interval_note: str
    predictions: list[Prediction]

    def as_json(self):
        return asdict(self)


def normalize(observations: Iterable[Observation]) -> list[Observation]:
    observations = sorted(observations, key=lambda row: row.day)
    if not observations:
        return []
    mapping = {}
    for row in observations:
        if row.day in mapping:
            raise ValueError(f"Duplicate date: {row.day}")
        if not np.isfinite(row.units) or row.units < 0:
            raise ValueError("Sales quantities must be finite and nonnegative")
        mapping[row.day] = float(row.units)
    current = observations[0].day
    end = observations[-1].day
    normalized = []
    while current <= end:
        normalized.append(Observation(current, mapping.get(current, 0.0)))
        current += timedelta(days=1)
    return normalized


def _feature(day: date, history: list[float]) -> list[float]:
    if len(history) < 28:
        raise ValueError("At least 28 preceding days are needed for lag features")
    weekday = day.weekday()
    return [
        history[-1], history[-7], history[-14], history[-28],
        float(mean(history[-7:])),
        float(mean(history[-28:])),
        sin(2 * pi * weekday / 7), cos(2 * pi * weekday / 7),
    ]


def _fit_ml(rows: list[Observation]) -> RandomForestRegressor:
    features = []
    values = []
    all_values = [item.units for item in rows]
    for index in range(28, len(rows)):
        features.append(_feature(rows[index].day, all_values[:index]))
        values.append(rows[index].units)
    if len(features) < MIN_TRAIN_EXAMPLES:
        raise ValueError("Too little history to train and test this model")
    model = RandomForestRegressor(
        n_estimators=96,
        max_depth=6,
        min_samples_leaf=3,
        max_features=1.0,
        random_state=SEED,
        n_jobs=1,
    )
    model.fit(features, values)
    return model


def _recursive_predict(
    method: str, model: RandomForestRegressor | None, history: list[float],
    first_day: date, days: int,
) -> list[float]:
    buffer = list(history)
    predictions = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        if method == "ml":
            assert model is not None
            value = float(model.predict([_feature(day, buffer)])[0])
        else:
            value = float(mean(buffer[-7:]))
        value = max(0.0, value)
        predictions.append(value)
        buffer.append(value)
    return predictions


def forecast_daily(observations: Iterable[Observation], horizon: int = 30) -> ForecastResult:
    if not (1 <= horizon <= 60):
        raise ValueError("Horizon must be between 1 and 60 days")
    rows = normalize(observations)
    no_intervals = "No statistically calibrated prediction interval is available."
    if len(rows) < MIN_HISTORY:
        return ForecastResult(
            status="insufficient_history", selected_method=None,
            history_days=len(rows), evaluation_days=0,
            baseline_mae=None, ml_mae=None, interval_note=no_intervals,
            predictions=[],
        )

    # Fixed chronological cutoff; the model and baseline see exactly the same
    # historical observations, then recursively predict the entire held-out span.
    evaluation_days = min(28, max(14, len(rows) // 5))
    training = rows[:-evaluation_days]
    actual = [row.units for row in rows[-evaluation_days:]]
    start = rows[-evaluation_days].day
    train_history = [row.units for row in training]
    model = _fit_ml(training)
    baseline_eval = _recursive_predict("baseline", None, train_history, start, evaluation_days)
    ml_eval = _recursive_predict("ml", model, train_history, start, evaluation_days)
    baseline_mae = float(mean(abs(a - b) for a, b in zip(actual, baseline_eval)))
    ml_mae = float(mean(abs(a - b) for a, b in zip(actual, ml_eval)))

    # Prefer the interpretable baseline if ML does not show meaningful improvement.
    selected = "ml" if ml_mae < baseline_mae * 0.98 else "baseline"
    # Train on all available past data after evaluation; do not incorporate
    # future labels. Forecast starts the day after the last observed day.
    final_model = _fit_ml(rows) if selected == "ml" else None
    values = _recursive_predict(
        selected, final_model, [row.units for row in rows],
        rows[-1].day + timedelta(days=1), horizon,
    )
    errors = [abs(a - b) for a, b in zip(actual, ml_eval if selected == "ml" else baseline_eval)]
    error_scale = float(np.quantile(errors, 0.90))
    predictions = []
    for index, value in enumerate(values):
        # This range is an illustrative error-based band, NOT a calibrated CI.
        width = error_scale * (1 + index / 30)
        predictions.append(Prediction(
            day=(rows[-1].day + timedelta(days=index + 1)).isoformat(),
            units=round(value, 2),
            lower_heuristic=round(max(0.0, value - width), 2),
            upper_heuristic=round(value + width, 2),
        ))
    return ForecastResult(
        status="evaluated", selected_method=selected,
        history_days=len(rows), evaluation_days=evaluation_days,
        baseline_mae=round(baseline_mae, 4), ml_mae=round(ml_mae, 4),
        interval_note=(
            "Error bands use the 90th percentile of absolute errors on one chronological "
            "holdout, widened heuristically over the horizon. These are NOT "
            "statistically calibrated confidence intervals."
        ), predictions=predictions,
    )
