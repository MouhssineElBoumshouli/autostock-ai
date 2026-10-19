"""Puts it together: for every part in every branch and every horizon, test the methods that fit
its demand type on its own past, pick one, and forecast with a low-high range. Pure numpy: no database."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.forecast.backtest import actuals, backtest_origins, choose, forecast_range, mase_scale, score
from app.forecast.boosting import boosting_forecast, prepare
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


@dataclass
class SeriesForecast:
    row: int
    horizon: int
    demand_type: str
    method: str
    quantity: float  # pieces expected over the whole horizon
    low: float
    high: float
    method_wape: float | None
    baseline_wape: float | None
    method_mase: float | None
    baseline_mase: float | None
    windows: int
    reason: str
    method_error: float | None = None  # pieces off in the backtest, for reports
    baseline_error: float | None = None
    every_method: dict[str, float] = field(default_factory=dict)  # each method's forecast, for reports


def forecast_all(demand: np.ndarray, first_day: date) -> list[SeriesForecast]:
    days = demand.shape[1]
    data = prepare(demand, first_day)
    types = [demand_type(row) for row in demand]
    scales = [mase_scale(row) for row in demand]
    local = {name: method(demand) for name, method in LOCAL_METHODS.items()}

    results = []
    for horizon in HORIZONS:
        origins = backtest_origins(days, horizon)
        columns = [*origins, days]  # the past windows, then today
        predictions = {name: table[:, columns] for name, table in local.items()}
        predictions["boosting"] = np.column_stack([boosting_forecast(data, o, horizon) for o in columns])
        rates, known, usable = actuals(data, origins, horizon)
        for row in range(demand.shape[0]):
            past = {name: (table[row, :-1][usable[row]], table[row, -1]) for name, table in predictions.items()}
            results.append(
                _forecast_one(row, horizon, types[row], past, rates[row][usable[row]], known[row][usable[row]], scales[row])
            )
    return results


def _forecast_one(row, horizon, kind, past, actual, known, scale) -> SeriesForecast:
    names = [BASELINE, *CANDIDATES[kind]]
    scores = {name: score(past[name][0], actual, known, scale) for name in names}
    method, reason = choose(scores, BASELINE, len(actual))
    if np.isnan(past[method][1]):  # cannot happen for local methods; boosting may lack history
        method, reason = BASELINE, "The chosen method had no forecast for today: using the 4-week average."
    quantity = float(past[method][1]) * horizon
    low, high = forecast_range(quantity, past[method][0], actual, horizon)
    chosen, base = scores[method], scores[BASELINE]
    return SeriesForecast(
        row=row,
        horizon=horizon,
        demand_type=kind,
        method=method,
        quantity=quantity,
        low=low,
        high=high,
        method_wape=chosen.wape if chosen else None,
        baseline_wape=base.wape if base else None,
        method_mase=chosen.mase if chosen else None,
        baseline_mase=base.mase if base else None,
        windows=len(actual),
        reason=reason,
        method_error=chosen.error if chosen else None,
        baseline_error=base.error if base else None,
        every_method={name: float(value) * horizon for name, (_, value) in past.items()},
    )
