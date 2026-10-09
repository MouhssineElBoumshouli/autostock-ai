from datetime import date, timedelta

import pytest

from ml.forecast import BASELINE_METHODS, Observation, forecast_daily, normalize


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
    assert result.selected_method in BASELINE_METHODS or result.selected_method == "random_forest"
    assert result.baseline_method in BASELINE_METHODS
    assert result.baseline_mae >= 0
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


def test_supported_horizons_return_the_requested_number_of_days():
    data = sample(days=180)
    for horizon in (7, 30, 60):
        result = forecast_daily(data, horizon=horizon)
        assert result.status == "evaluated"
        assert len(result.predictions) == horizon
        assert result.evaluation_days == horizon
        assert f"{horizon}-day chronological holdout" in result.interval_note
        assert "not an independent accuracy estimate" in result.interval_note


@pytest.mark.parametrize("horizon", [7, 30, 60])
def test_horizon_aligned_evaluation_handles_intermittent_demand(horizon):
    rows = [
        Observation(date(2026, 1, 1) + timedelta(days=i), 6.0 if i % 14 == 0 else 0.0)
        for i in range(90)
    ]

    result = forecast_daily(rows, horizon=horizon)

    assert result.status == "intermittent_baseline"
    assert result.demand_pattern == "intermittent"
    assert result.evaluation_days == horizon
    assert result.ml_mae is None
    assert len(result.predictions) == horizon


def test_sixty_day_holdout_with_minimum_history_reports_baseline_only():
    result = forecast_daily(sample(days=90), horizon=60)

    assert result.status == "baseline_only"
    assert result.evaluation_days == 60
    assert result.ml_mae is None
    assert "random forest was skipped" in result.interval_note


def test_zero_sales_is_not_invented_into_positive_demand():
    result = forecast_daily([
        Observation(date(2026, 1, 1) + timedelta(days=i), 0.0)
        for i in range(110)
    ], horizon=7)
    assert result.status == "no_observed_demand"
    assert result.predictions == []
    assert result.selected_method is None


def test_intermittent_history_uses_sparse_demand_baseline_without_random_forest():
    rows = [
        Observation(date(2026, 1, 1) + timedelta(days=i), 6.0 if i % 14 == 0 else 0.0)
        for i in range(210)
    ]

    result = forecast_daily(rows, horizon=30)

    assert result.status == "intermittent_baseline"
    assert result.demand_pattern == "intermittent"
    assert result.selected_method in BASELINE_METHODS
    assert result.ml_mae is None
    assert len(result.predictions) == 30
    assert all(point.units >= 0 for point in result.predictions)


def test_model_evaluation_fits_only_before_the_chronological_holdout(monkeypatch):
    import ml.forecast as forecast_module

    rows = sample(days=150)
    fitted_cutoffs = []
    real_fit = forecast_module._fit_ml

    def capture_training_cutoff(training_rows):
        fitted_cutoffs.append(training_rows[-1].day)
        return real_fit(training_rows)

    monkeypatch.setattr(forecast_module, "_fit_ml", capture_training_cutoff)
    result = forecast_module.forecast_daily(rows, horizon=7)

    holdout_start = rows[-result.evaluation_days].day
    assert fitted_cutoffs
    assert fitted_cutoffs[0] < holdout_start


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
