"""Chronological demand forecasting shared by the offline evaluator and Odoo worker."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import cos, pi, sin
from statistics import mean
from typing import Iterable

import numpy as np
from sklearn.ensemble import RandomForestRegressor

MODEL_VERSION = "autostock-demand-v2.1.0"
MIN_HISTORY = 90
MIN_TRAIN_EXAMPLES = 30
MIN_TRAINING_DAYS = 28
MAX_HORIZON = 60
INTERMITTENT_ADI_THRESHOLD = 1.32
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
    baseline_method: str | None
    demand_pattern: str
    history_days: int
    nonzero_days: int
    evaluation_days: int
    baseline_mae: float | None
    ml_mae: float | None
    interval_note: str
    predictions: list[Prediction]

    def as_json(self):
        return asdict(self)


def normalize(observations: Iterable[Observation]) -> list[Observation]:
    rows = sorted(observations, key=lambda row: row.day)
    if not rows:
        return []
    mapping = {}
    for row in rows:
        if row.day in mapping:
            raise ValueError(f"Duplicate date: {row.day}")
        if not np.isfinite(row.units) or row.units < 0:
            raise ValueError("Sales quantities must be finite and nonnegative")
        mapping[row.day] = float(row.units)
    current = rows[0].day
    end = rows[-1].day
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
        # Each example uses only observations strictly before its target day.
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


def _croston_sba_rate(history: list[float], alpha: float = 0.1) -> float:
    """Return Croston's bias-adjusted rate for intermittent nonnegative demand."""
    event_days = [index for index, value in enumerate(history) if value > 0]
    if not event_days:
        return 0.0
    first = event_days[0]
    smoothed_size = history[first]
    smoothed_interval = float(first + 1)
    previous = first
    for index in event_days[1:]:
        interval = float(index - previous)
        smoothed_size = alpha * history[index] + (1 - alpha) * smoothed_size
        smoothed_interval = alpha * interval + (1 - alpha) * smoothed_interval
        previous = index
    return max(0.0, (smoothed_size / smoothed_interval) * (1 - alpha / 2))


BASELINE_METHODS = ("trailing_mean_7", "seasonal_naive_7", "croston_sba")


def _recursive_predict(
    method: str,
    model: RandomForestRegressor | None,
    history: list[float],
    first_day: date,
    days: int,
) -> list[float]:
    buffer = list(history)
    croston_rate = _croston_sba_rate(buffer) if method == "croston_sba" else None
    predictions = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        if method == "random_forest":
            if model is None:
                raise ValueError("The random forest model was not fitted")
            value = float(model.predict([_feature(day, buffer)])[0])
        elif method == "trailing_mean_7":
            value = float(mean(buffer[-7:]))
        elif method == "seasonal_naive_7":
            value = float(buffer[-7])
        elif method == "croston_sba":
            value = float(croston_rate or 0.0)
        else:
            raise ValueError(f"Unsupported forecast method: {method}")
        value = max(0.0, value)
        predictions.append(value)
        buffer.append(value)
    return predictions


def _mae(actual: list[float], predicted: list[float]) -> float:
    return float(mean(abs(observed - estimate) for observed, estimate in zip(actual, predicted)))


def forecast_daily(observations: Iterable[Observation], horizon: int = 30) -> ForecastResult:
    if not (1 <= horizon <= MAX_HORIZON):
        raise ValueError(f"Horizon must be between 1 and {MAX_HORIZON} days")
    rows = normalize(observations)
    no_intervals = "No statistically calibrated prediction interval is available."
    nonzero_days = sum(row.units > 0 for row in rows)
    if len(rows) < MIN_HISTORY:
        return ForecastResult(
            status="insufficient_history", selected_method=None, baseline_method=None,
            demand_pattern="insufficient", history_days=len(rows), nonzero_days=nonzero_days,
            evaluation_days=0, baseline_mae=None, ml_mae=None,
            interval_note=no_intervals, predictions=[],
        )
    if not nonzero_days:
        return ForecastResult(
            status="no_observed_demand", selected_method=None, baseline_method=None,
            demand_pattern="zero", history_days=len(rows), nonzero_days=0,
            evaluation_days=0, baseline_mae=None, ml_mae=None,
            interval_note="No completed deliveries were observed in the configured history window; no numeric forecast is shown.",
            predictions=[],
        )

    # Measure the selected forecast length on a chronological holdout of the
    # same length. Keep enough history to build the lag features; when that
    # leaves too few examples for ML, evaluate the transparent baselines only.
    evaluation_days = min(horizon, max(0, len(rows) - MIN_TRAINING_DAYS))
    if evaluation_days == 0:
        return ForecastResult(
            status="insufficient_history", selected_method=None, baseline_method=None,
            demand_pattern="insufficient", history_days=len(rows), nonzero_days=nonzero_days,
            evaluation_days=0, baseline_mae=None, ml_mae=None,
            interval_note=no_intervals, predictions=[],
        )
    training = rows[:-evaluation_days]
    actual = [row.units for row in rows[-evaluation_days:]]
    start = rows[-evaluation_days].day
    train_history = [row.units for row in training]

    # All candidate methods see the same chronological holdout and training cutoff.
    baseline_predictions = {
        method: _recursive_predict(method, None, train_history, start, evaluation_days)
        for method in BASELINE_METHODS
    }
    baseline_scores = {
        method: _mae(actual, predicted)
        for method, predicted in baseline_predictions.items()
    }
    baseline_method = min(BASELINE_METHODS, key=lambda method: (baseline_scores[method], method))
    baseline_mae = baseline_scores[baseline_method]
    mean_interval = len(training) / max(1, sum(value > 0 for value in train_history))
    intermittent = mean_interval >= INTERMITTENT_ADI_THRESHOLD
    ml_mae = None
    ml_eval = None
    final_model = None

    # Sparse series use intermittent-demand baselines. A random forest trained
    # mostly on zeroes is not allowed to turn rare events into confident demand.
    if not intermittent:
        try:
            model = _fit_ml(training)
            ml_eval = _recursive_predict("random_forest", model, train_history, start, evaluation_days)
            ml_mae = _mae(actual, ml_eval)
        except ValueError:
            ml_mae = None

    if ml_mae is not None and ml_mae < baseline_mae * 0.98:
        selected_method = "random_forest"
        selected_eval = ml_eval
        final_model = _fit_ml(rows)
    else:
        selected_method = baseline_method
        selected_eval = baseline_predictions[baseline_method]

    values = _recursive_predict(
        selected_method, final_model, [row.units for row in rows],
        rows[-1].day + timedelta(days=1), horizon,
    )
    errors = [abs(observed - estimate) for observed, estimate in zip(actual, selected_eval)]
    error_scale = float(np.quantile(errors, 0.90))
    predictions = []
    for index, value in enumerate(values):
        # This band is descriptive only and is never represented as a confidence interval.
        width = error_scale * (1 + index / 30)
        predictions.append(Prediction(
            day=(rows[-1].day + timedelta(days=index + 1)).isoformat(),
            units=round(value, 4),
            lower_heuristic=round(max(0.0, value - width), 4),
            upper_heuristic=round(value + width, 4),
        ))

    pattern = "intermittent" if intermittent else "regular"
    if intermittent:
        status = "intermittent_baseline"
        interval_note = (
            f"Intermittent history: random forest training was skipped. Baseline comparison uses a "
            f"{evaluation_days}-day chronological holdout matching the requested horizon. The same single "
            "holdout selects the method and supplies the reported MAE, so it is comparison evidence, not an "
            "independent accuracy estimate. The displayed range is heuristic, not calibrated."
        )
    else:
        status = "evaluated" if ml_mae is not None else "baseline_only"
        holdout_note = (
            f"The baseline and model comparison uses a {evaluation_days}-day chronological holdout matching "
            "the requested horizon. The same single holdout selects the method and supplies the reported MAE, "
            "so it is comparison evidence, not an independent accuracy estimate."
        )
        model_note = (
            " A random forest was evaluated."
            if ml_mae is not None
            else " A random forest was skipped because the pre-holdout training window did not contain enough examples."
        )
        interval_note = (
            holdout_note + model_note + " The error band uses the 90th percentile of absolute holdout errors, "
            "widened heuristically over the horizon; it is NOT a statistically calibrated confidence interval."
        )
    return ForecastResult(
        status=status, selected_method=selected_method, baseline_method=baseline_method,
        demand_pattern=pattern, history_days=len(rows), nonzero_days=nonzero_days,
        evaluation_days=evaluation_days, baseline_mae=round(baseline_mae, 4),
        ml_mae=round(ml_mae, 4) if ml_mae is not None else None,
        interval_note=interval_note, predictions=predictions,
    )
