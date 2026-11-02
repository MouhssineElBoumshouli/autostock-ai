"""Puts it together, for every horizon:
1. test the methods that fit each demand type on the past of every part,
2. pick one method per demand type from the pooled results of all its parts (the baseline unless
   another method clearly beats it), and widen that type's ranges until they catch 80%,
3. forecast every part in every branch, keeping its own score against the baseline.
Pure numpy: no database."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.forecast.backtest import (
    MIN_WINDOWS,
    Score,
    actuals,
    backtest_origins,
    choose_for_type,
    forecast_range,
    mase_scale,
    range_gaps,
    score,
    widen_factor,
)
from app.forecast.boosting import Prepared, boosting_forecasts, prepare
from app.forecast.demand_types import demand_type
from app.forecast.methods import croston, exponential_smoothing, four_week_average, last_week, sba, tsb

HORIZONS = (7, 30, 60)
BASELINE = "four_week_average"
LOCAL_METHODS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    BASELINE: four_week_average,
    "last_week": last_week,
    "exponential_smoothing": exponential_smoothing,
    "croston": croston,
    "sba": sba,
    "tsb": tsb,
}
# Which methods compete for each demand type (the baseline always takes part).
CANDIDATES = {
    "smooth": ["last_week", "exponential_smoothing", "boosting"],
    "erratic": ["last_week", "exponential_smoothing", "boosting"],
    "slow": ["exponential_smoothing", "croston", "sba", "tsb", "boosting"],
    "lumpy": ["exponential_smoothing", "croston", "sba", "tsb", "boosting"],
    "no_sales": [],
}
ROWS_AT_A_TIME = 5000  # the simple methods work on this many part-branch rows at a time


@dataclass
class SeriesForecast:
    row: int
    horizon: int
    demand_type: str
    method: str
    quantity: float  # pieces expected over the whole horizon
    low: float
    high: float
    method_wape: float | None  # this part's own past score with the method used
    baseline_wape: float | None
    method_mase: float | None
    baseline_mase: float | None
    windows: int
    reason: str
    widen: float = 1.0  # how much this demand type's ranges were widened to catch 80%
    method_error: float | None = None  # pieces off in the backtest, for reports
    baseline_error: float | None = None
    every_method: dict[str, float] = field(default_factory=dict)  # each method's forecast, for reports


@dataclass
class Past:
    """One part in one branch, for one horizon: what each method forecast and what really sold."""

    kind: str
    predicted: dict[str, np.ndarray]  # per method: daily rate forecast for each tested window
    today: dict[str, float]  # every method: daily rate forecast from today
    actual: np.ndarray
    scores: dict[str, Score | None]


def forecast_all(demand: np.ndarray, first_day: date) -> list[SeriesForecast]:
    """`demand` may be handed over (run_forecasts does): it is let go of once read, which frees a
    big shop's ~0.75 GB before the slow part (learning the boosting models)."""
    days = demand.shape[1]
    data = prepare(demand, first_day)
    kinds = [demand_type(row) for row in demand]
    scales = [mase_scale(row) for row in demand]
    needed = sorted({day for horizon in HORIZONS for day in [*backtest_origins(days, horizon), days]})
    local = local_forecasts(demand, needed)
    del demand
    results = []
    for horizon in HORIZONS:
        local_columns = [needed.index(day) for day in [*backtest_origins(days, horizon), days]]
        results += _forecast_horizon(horizon, data, kinds, scales, {name: table[:, local_columns] for name, table in local.items()})
    return results


def _forecast_horizon(horizon: int, data: Prepared, kinds: list[str], scales: list[float], tables: dict[str, np.ndarray]) -> list[SeriesForecast]:
    """Every row's forecast for one horizon. `tables`: each simple method's forecast from each past
    window, then from today. Its own function, so this horizon's working tables and per-part
    objects are freed before the next horizon's models are learned."""
    days = data.days
    origins = backtest_origins(days, horizon)
    tables["boosting"] = boosting_forecasts(data, [*origins, days], horizon)
    rates, known, usable = actuals(data, origins, horizon)

    pasts = []
    for row, kind in enumerate(kinds):
        use = usable[row]
        names = [BASELINE, *CANDIDATES[kind]]
        predicted = {name: tables[name][row, :-1][use] for name in names}
        actual = rates[row][use]
        scores = {name: score(predicted[name], actual, known[row][use], scales[row]) for name in names}
        pasts.append(Past(kind, predicted, {name: float(table[row, -1]) for name, table in tables.items()}, actual, scores))

    choices = {kind: _choose(kind, pasts, horizon) for kind in CANDIDATES}
    return [_forecast_one(row, horizon, past, *choices[past.kind]) for row, past in enumerate(pasts)]


def local_forecasts(demand: np.ndarray, days: list[int], names: Iterable[str] = LOCAL_METHODS) -> dict[str, np.ndarray]:
    """Each simple method's forecast from each of `days` (columns of the methods' tables), a few
    thousand rows at a time: each row is worked out on its own, and whole tables for every day
    of a big shop would not fit in memory."""
    chunks = range(0, max(len(demand), 1), ROWS_AT_A_TIME)
    return {
        name: np.vstack([LOCAL_METHODS[name](demand[start : start + ROWS_AT_A_TIME])[:, days] for start in chunks])
        for name in names
    }


def _choose(kind: str, pasts: list[Past], horizon: int) -> tuple[str, str, float]:
    """The method for one demand type, why, and how much to widen its ranges."""
    tested = [p for p in pasts if p.kind == kind and len(p.actual) >= MIN_WINDOWS and all(p.scores.values())]
    names = [BASELINE, *CANDIDATES[kind]]
    pooled = {name: sum(p.scores[name].error for p in tested) for name in names}
    method, reason = choose_for_type(pooled, BASELINE, kind, len(tested))
    widen = widen_factor([(p.predicted[method], p.actual) for p in tested], horizon)
    return method, reason, widen


def _forecast_one(row: int, horizon: int, past: Past, method: str, reason: str, widen: float) -> SeriesForecast:
    windows = len(past.actual)
    if windows < MIN_WINDOWS:
        method, reason = BASELINE, f"Too little history to test ({windows} of {MIN_WINDOWS} past windows): using the 4-week average."
    elif np.isnan(past.today[method]):  # boosting may lack history for a part
        method, reason = BASELINE, "The chosen method had no forecast for this part: using the 4-week average."
    quantity = past.today[method] * horizon
    below, above = range_gaps(quantity, past.predicted[method], past.actual, horizon)
    low, high = forecast_range(quantity, below, above, widen)
    chosen, base = past.scores[method], past.scores[BASELINE]
    return SeriesForecast(
        row=row,
        horizon=horizon,
        demand_type=past.kind,
        method=method,
        quantity=quantity,
        low=low,
        high=high,
        method_wape=chosen.wape if chosen else None,
        baseline_wape=base.wape if base else None,
        method_mase=chosen.mase if chosen else None,
        baseline_mase=base.mase if base else None,
        windows=windows,
        reason=reason,
        widen=widen,
        method_error=chosen.error if chosen else None,
        baseline_error=base.error if base else None,
        every_method={name: value * horizon for name, value in past.today.items()},
    )
