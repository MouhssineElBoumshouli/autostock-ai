from datetime import date, timedelta

import pytest

from ml.forecast import Observation, forecast_daily, normalize


def sample(days=140, base=15):
    return [Observation(date(2026, 1, 1) + timedelta(days=i),
                        float(base + (4 if i % 7 in (5, 6) else 0)))
            for i in range(days)]


def test_insufficient_history_never_invents_predictions():
    result = forecast_daily(sample(40), 30)
    assert result.status == "insufficient_history"
    assert result.predictions == []
    assert result.baseline_mae is None


def test_evaluated_forecast_stays_nonnegative_and_forward_only():
    data = sample()
    result = forecast_daily(data, horizon=30)
    assert result.status == "evaluated"
    assert result.selected_method in {"ml", "baseline"}
    assert result.evaluation_days > 0
    assert result.baseline_mae >= 0
    assert result.ml_mae >= 0
    assert len(result.predictions) == 30
    assert result.predictions[0].day == (data[-1].day + timedelta(days=1)).isoformat()
    assert all(p.units >= 0 and p.lower_heuristic >= 0 and p.upper_heuristic >= p.units
               for p in result.predictions)
    assert "NOT" in result.interval_note


def test_prediction_reproducible():
    first = forecast_daily(sample(100), horizon=7).as_json()
    second = forecast_daily(sample(100), horizon=7).as_json()
    assert first == second


def test_zero_sales_is_not_invented_into_positive_demand():
    result = forecast_daily([
        Observation(date(2026, 1, 1) + timedelta(days=i), 0.0)
        for i in range(110)
    ], horizon=7)
    assert all(point.units == 0 for point in result.predictions)


def test_missing_calendar_dates_filled_with_zero():
    rows = [Observation(date(2026, 1, 1), 3), Observation(date(2026, 1, 3), 2)]
    normal = normalize(rows)
    assert len(normal) == 3
    assert normal[1].units == 0


def test_duplicate_date_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        normalize([Observation(date(2026, 1, 1), 1), Observation(date(2026, 1, 1), 2)])


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_sales_rejected(value):
    with pytest.raises(ValueError, match="nonnegative"):
        normalize([Observation(date(2026, 1, 1), value)])


@pytest.mark.parametrize("horizon", [0, 61])
def test_invalid_horizon_rejected(horizon):
    with pytest.raises(ValueError, match="Horizon"):
        forecast_daily(sample(), horizon=horizon)
