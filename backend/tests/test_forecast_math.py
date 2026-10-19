"""Every forecast calculation, on small hand-made numbers (no database)."""

from datetime import date, timedelta

import numpy as np
import pytest

from app.forecast.backtest import (
    actuals,
    backtest_origins,
    choose_for_type,
    forecast_range,
    range_gaps,
    widen_factor,
    mase_scale,
    score,
)
from app.forecast.boosting import FIRST_TRAINING_DAY, boosting_forecast, prepare, window_average
from app.forecast.demand_types import adi_and_cv2, demand_type, weekly_totals
from app.forecast.engine import CANDIDATES, HORIZONS, forecast_all
from app.forecast.history import demand_matrix
from app.forecast.methods import (
    croston,
    exponential_smoothing,
    four_week_average,
    last_week,
    rolling_average,
    sba,
    tsb,
)

NAN = np.nan
DAY0 = date(2026, 1, 5)


def row(values) -> np.ndarray:
    return np.array([values], dtype=float)


# --- cleaning -----------------------------------------------------------------------------------


def test_cleaning_adds_up_sales_per_day_and_counts_returns_as_nothing_sold():
    sales = [(0, DAY0, 2), (0, DAY0, 3), (0, DAY0 + timedelta(days=2), 1), (0, DAY0 + timedelta(days=3), -4)]
    demand = demand_matrix(sales, [], 1, DAY0, 5)
    assert demand[0].tolist() == [5, 0, 1, 0, 0]


def test_days_before_the_first_sale_are_unknown_not_zero():
    demand = demand_matrix([(0, DAY0 + timedelta(days=2), 1)], [], 1, DAY0, 4)
    assert np.isnan(demand[0, :2]).all() and demand[0, 2:].tolist() == [1, 0]


def test_stock_out_days_are_unknown_not_zero_sales():
    sales = [(0, DAY0, 1)]
    outs = [(0, DAY0 + timedelta(days=2), DAY0 + timedelta(days=3)), (0, DAY0 + timedelta(days=5), DAY0 + timedelta(days=99))]
    demand = demand_matrix(sales, outs, 1, DAY0, 7)
    assert demand[0, :2].tolist() == [1, 0]
    assert np.isnan(demand[0, [2, 3, 5, 6]]).all() and demand[0, 4] == 0


def test_a_part_with_no_sales_is_all_unknown():
    assert np.isnan(demand_matrix([], [], 1, DAY0, 3)).all()


# --- sorting by how a part sells ----------------------------------------------------------------


def test_weekly_totals_count_back_from_the_last_day_and_scale_weeks_with_unknown_days():
    history = np.array([9.0] + [1.0] * 7 + [2.0, NAN, NAN, NAN, NAN, NAN, NAN])
    assert weekly_totals(history).tolist() == [7.0, 14.0]  # the lone first day is left out


def test_adi_and_cv2():
    weekly = np.concatenate([[5, 0, 0, 0, 0, 0, 0], [0] * 7, [15, 0, 0, 0, 0, 0, 0], [0] * 7]).astype(float)
    adi, cv2 = adi_and_cv2(weekly)
    assert adi == 2.0  # 4 weeks, 2 with sales
    assert cv2 == pytest.approx(0.25)  # sizes 5 and 15: std 5, mean 10


@pytest.mark.parametrize(
    "weeks, expected",
    [
        ([10, 11, 9, 10, 12, 10, 9, 11], "smooth"),  # every week, steady
        ([1, 30, 2, 25, 1, 40, 3, 1], "erratic"),  # every week, uneven
        ([3, 0, 0, 3, 0, 0, 3, 0], "slow"),  # rare, steady
        ([1, 0, 0, 20, 0, 0, 2, 0], "lumpy"),  # rare, uneven
        ([0, 0, 0, 0, 0, 0, 0, 0], "no_sales"),
    ],
)
def test_demand_types(weeks, expected):
    daily = np.concatenate([[w] + [0] * 6 for w in weeks]).astype(float)
    assert demand_type(daily) == expected


# --- methods ------------------------------------------------------------------------------------


def test_rolling_average_skips_unknown_days_and_never_looks_ahead():
    averages = rolling_average(row([2, NAN, 4, 6]), 3)
    assert np.isnan(averages[0, 0])  # nothing known before day 0
    assert averages[0, 1:].tolist() == [2, 2, 3, 5]  # column t uses days t-3 .. t-1


def test_four_week_average_falls_back_to_13_weeks_then_zero():
    history = np.concatenate([[7.0] * 10, [NAN] * 30])
    forecasts = four_week_average(row(history))
    assert forecasts[0, -1] == 7.0  # last 4 weeks unknown: uses the last 13 weeks
    assert forecasts[0, 0] == 0.0  # nothing known yet
    assert four_week_average(row([1.0] * 28 + [3.0] * 28))[0, -1] == 3.0


def test_last_week_is_last_weeks_daily_average():
    history = [9.0] * 21 + [0, 1, 2, 3, 4, 5, 6]
    assert last_week(row(history))[0, -1] == 3.0


def test_exponential_smoothing_follows_new_sales_slowly_and_skips_unknown_days():
    forecasts = exponential_smoothing(row([10, 10, NAN, 20]), alpha=0.1)
    assert forecasts[0].tolist() == pytest.approx([0, 10, 10, 10, 11])


def test_croston_divides_sale_size_by_days_between_sales():
    history = [4, 0, 0, 0] * 10
    assert croston(row(history))[0, -1] == pytest.approx(1.0)
    assert sba(row(history))[0, -1] == pytest.approx(0.95)  # 5% lower: Croston's known bias


def test_croston_does_not_count_unknown_days_as_days_without_sales():
    with_gap = [4, 0, 0, 0] * 5 + [4, NAN, NAN, NAN, NAN, NAN, 0, 0, 0]
    assert croston(row(with_gap + [4]))[0, -1] == pytest.approx(1.0)


def test_tsb_fades_when_a_part_stops_selling_but_croston_does_not():
    history = [4, 0, 0, 0] * 10 + [0] * 60
    assert tsb(row(history))[0, -1] < 0.05
    assert croston(row(history))[0, -1] == pytest.approx(1.0)
    assert tsb(row([4, 0, 0, 0] * 30))[0, -1] == pytest.approx(1.0, abs=0.2)


def test_every_method_gives_one_more_column_than_days():
    demand = np.array([[1.0, 0, 2, NAN], [0, 0, 1, 0]])
    for method in (four_week_average, last_week, exponential_smoothing, croston, sba, tsb):
        result = method(demand)
        assert result.shape == (2, 5) and not np.isnan(result).any()


def seasonal_panel(rows: int = 40, days: int = 500) -> np.ndarray:
    rng = np.random.default_rng(0)
    t = np.arange(days)
    level = rng.uniform(1, 5, (rows, 1))
    return rng.poisson(level * (1 + 0.8 * np.sin(2 * np.pi * t / 365))).astype(float)


def test_boosting_learns_across_parts_and_never_uses_days_after_the_forecast_day():
    demand = seasonal_panel()
    origin = 400
    forecast = boosting_forecast(prepare(demand, DAY0), origin, 30)
    assert forecast.shape == (40,) and np.isfinite(forecast).all() and (forecast >= 0).all()
    changed = demand.copy()
    changed[:, origin:] = 1000  # the future changes; the forecast made before it must not
    assert np.allclose(boosting_forecast(prepare(changed, DAY0), origin, 30), forecast)


def test_boosting_gives_nothing_without_enough_history():
    demand = seasonal_panel(rows=2, days=150)
    assert np.isnan(boosting_forecast(prepare(demand, DAY0), 120, 30)).all()


def test_window_average_ignores_unknown_days():
    data = prepare(row([2, NAN, 4, 0]), DAY0)
    assert window_average(data, 0, 3)[0] == 3.0
    assert np.isnan(window_average(data, 1, 2)[0])


# --- backtest -----------------------------------------------------------------------------------


def test_backtest_windows_are_in_time_order_and_end_before_the_history_does():
    origins = backtest_origins(500, 30)
    assert origins == sorted(origins) and len(origins) == 12
    assert origins[-1] + 30 == 500 and origins[1] - origins[0] == 7
    assert all(o >= FIRST_TRAINING_DAY for o in backtest_origins(150, 30))


def test_actuals_only_count_windows_with_4_known_weeks_before_them():
    demand = np.concatenate([[NAN] * 100, [2.0] * 200])
    rates, known, usable = actuals(prepare(row(demand), DAY0), [110, 140], 30)
    assert rates[0].tolist() == [2.0, 2.0] and known[0].tolist() == [30, 30]
    assert usable[0].tolist() == [False, True]


def test_wape_and_mase():
    result = score(np.array([2.0, 4.0]), np.array([3.0, 3.0]), np.array([10, 10]), scale=0.5)
    assert result.error == 20  # off by 1 a day, 10 days, twice
    assert result.wape == pytest.approx(20 / 60)
    assert result.mase == pytest.approx(2.0)
    assert score(np.array([NAN, 1.0]), np.array([1.0, 1.0]), np.array([7, 7]), 1.0) is None
    assert score(np.array([1.0]), np.array([0.0]), np.array([7]), 0.0).wape is None


def test_mase_scale_is_the_usual_day_to_day_change():
    assert mase_scale(np.array([1, 3, NAN, 2, 2])) == pytest.approx(1.0)  # changes 2 and 0


def test_one_method_per_type_from_the_pooled_errors_of_its_parts():
    errors = {"four_week_average": 100.0, "croston": 80.0, "tsb": 90.0}
    method, reason = choose_for_type(errors, "four_week_average", "slow", 12)
    assert method == "croston" and "slow" in reason and "20%" in reason and "12 parts" in reason


def test_the_baseline_stays_unless_a_method_beats_it_by_5_percent():
    method, reason = choose_for_type({"four_week_average": 100.0, "croston": 97.0}, "four_week_average", "slow", 12)
    assert method == "four_week_average" and "no method beat" in reason
    method, reason = choose_for_type({"four_week_average": 0.0, "croston": 0.0}, "four_week_average", "slow", 12)
    assert method == "four_week_average"
    method, reason = choose_for_type({"four_week_average": 5.0, "croston": 1.0}, "four_week_average", "lumpy", 0)
    assert method == "four_week_average" and "Not enough" in reason


def test_range_gaps_come_from_past_misses():
    predicted = np.full(10, 1.0)
    actual = np.linspace(0.5, 3.0, 10)  # we under-forecast a lot, sometimes over
    below, above = range_gaps(30.0, predicted, actual, 30)
    misses = (actual - predicted) * 30
    assert below == pytest.approx(-np.quantile(misses, 0.1))
    assert above == pytest.approx(np.quantile(misses, 0.9))
    perfect = range_gaps(4.0, np.full(5, 1.0), np.full(5, 1.0), 7)  # chance still counts
    assert perfect == pytest.approx((1.28 * 2, 1.28 * 2))
    assert range_gaps(5.0, np.array([1.0]), np.array([1.0]), 7) == (5.0, 5.0)  # too few windows: 0 to double


def test_forecast_range_widens_and_is_never_negative():
    assert forecast_range(30.0, 7.5, 20.0) == (22.5, 50.0)
    assert forecast_range(30.0, 7.5, 20.0, widen=2.0) == (15.0, 70.0)
    assert forecast_range(1.0, 5.0, 5.0) == (0.0, 6.0)


def calm_then_wild(check_offsets) -> tuple[np.ndarray, np.ndarray]:
    learn = 1.0 + np.array([0.1, -0.1] * 4)
    return np.full(12, 1.0), np.concatenate([learn, 1.0 + np.array(check_offsets)])


def test_ranges_are_widened_until_newer_windows_land_inside_80_percent_of_the_time():
    # Older windows miss by about 3 pieces (chance alone allows 7); the newest miss by 6 and 9.
    cases = [calm_then_wild([-0.3, 0.3, -0.2, 0.2]) for _ in range(10)]
    assert widen_factor(cases, 30) == 1.3  # 9 / 7.01 = 1.28, rounded up to the next step
    assert widen_factor([calm_then_wild([0.1, -0.1, 0.1, -0.1])], 30) == 1.0  # already catches them
    assert widen_factor([(np.full(4, 1.0), np.full(4, 9.0))], 30) == 1.0  # too few windows to check
    assert widen_factor([], 30) == 1.0


# --- the whole engine ---------------------------------------------------------------------------


def test_engine_forecasts_every_row_for_every_horizon_with_a_range_and_a_reason():
    demand = seasonal_panel(rows=30, days=400)
    demand[0] = np.where(np.arange(400) % 20 == 0, 3.0, 0.0)  # a slow seller
    results = forecast_all(demand, DAY0)
    assert len(results) == 30 * len(HORIZONS)
    for r in results:
        assert r.low <= r.quantity <= r.high and r.reason
        assert r.method == "four_week_average" or r.method in CANDIDATES[r.demand_type]
    slow = [r for r in results if r.row == 0]
    assert all(r.demand_type == "slow" for r in slow)
    month = next(r for r in slow if r.horizon == 30)
    assert month.quantity == pytest.approx(30 * 3 / 20, rel=0.35)


def test_engine_uses_one_method_per_demand_type_but_keeps_each_parts_own_score():
    results = forecast_all(seasonal_panel(rows=30, days=400), DAY0)
    for horizon in HORIZONS:
        smooth = [r for r in results if r.horizon == horizon and r.demand_type == "smooth"]
        assert len(smooth) > 10 and len({r.method for r in smooth}) == 1
        assert len({r.baseline_wape for r in smooth}) > 1  # each part's own past score
        assert all(r.widen >= 1.0 for r in smooth)
