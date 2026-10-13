from datetime import date, datetime, timedelta, timezone

import pytest

from ml.inventory_risk import calculate_reorder, forecast_eligibility, recent_delivery_signal


def eligible_run(today: date, now: datetime) -> dict:
    return {
        "company_id": 2,
        "product_id": 5,
        "warehouse_id": 8,
        "source_type": "completed_deliveries",
        "state": "completed",
        "evaluation_status": "evaluated",
        "review_status": "reviewed",
        "horizon_days": 30,
        "evaluation_days": 30,
        "history_days": 120,
        "nonzero_days": 18,
        "history_end_date": today - timedelta(days=1),
        "source_cutoff": now - timedelta(hours=3),
    }


def test_reviewed_forecast_requires_exact_scope_freshness_and_lead_coverage():
    today = date(2026, 10, 9)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    run = eligible_run(today, now)
    dates = [(today + timedelta(days=day)).isoformat() for day in range(1, 31)]

    assert forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=8,
        lead_time_days=21, today=today, now=now, point_dates=dates,
    )[0]
    assert not forecast_eligibility(
        run, company_id=3, product_id=5, warehouse_id=8,
        lead_time_days=21, today=today, now=now, point_dates=dates,
    )[0]
    assert not forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=9,
        lead_time_days=21, today=today, now=now, point_dates=dates,
    )[0]

    run["review_status"] = "unreviewed"
    valid, reason = forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=8,
        lead_time_days=7, today=today, now=now, point_dates=dates,
    )
    assert not valid and "not been reviewed" in reason


def test_reviewed_forecast_requires_its_source_history_to_remain_current():
    today = date(2026, 10, 9)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    run = eligible_run(today, now)
    dates = [(today + timedelta(days=day)).isoformat() for day in range(1, 31)]

    valid, reason = forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=8,
        lead_time_days=21, today=today, now=now, point_dates=dates,
        source_current=False,
    )

    assert not valid
    assert "saved history no longer matches" in reason


@pytest.mark.parametrize(
    ("changes", "expected_fragment"),
    [
        ({"source_type": "synthetic_demo"}, "Synthetic forecasts"),
        ({"source_cutoff": datetime(2026, 9, 1, tzinfo=timezone.utc)}, "older than 14 days"),
        ({"history_days": 89}, "fewer than 90"),
        ({"nonzero_days": 6}, "fewer than 7"),
        ({"evaluation_days": 7}, "full horizon"),
    ],
)
def test_unreliable_forecast_reasons_are_explicit(changes, expected_fragment):
    today = date(2026, 10, 9)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    run = eligible_run(today, now)
    run.update(changes)
    valid, reason = forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=8,
        lead_time_days=7, today=today, now=now,
        point_dates=[today + timedelta(days=day) for day in range(1, 31)],
    )
    assert not valid
    assert expected_fragment in reason


def test_forecast_must_cover_every_day_needed_through_receipt():
    today = date(2026, 10, 9)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    run = eligible_run(today, now)
    dates = [today + timedelta(days=day) for day in range(1, 31) if day != 11]
    valid, reason = forecast_eligibility(
        run, company_id=2, product_id=5, warehouse_id=8,
        lead_time_days=21, today=today, now=now, point_dates=dates,
    )
    assert not valid
    assert "every day" in reason


def test_forecast_deduplicates_committed_sale_outgoing_from_odoo_projection():
    result = calculate_reorder(
        on_hand=18,
        free_qty=12,
        projected_at_receipt=16,  # Odoo already includes 4 confirmed outgoing units.
        committed_customer_outbound=4,
        forecast_demand=13,
        forecast_usable=True,
        minimum_threshold=8,
        target_stock=20,
        product_rounding=1,
    )
    assert result["additional_forecast_demand"] == 9
    assert result["projected_after_demand"] == 7
    assert result["recommended_qty"] == 13
    assert result["target_gap"] == 13
    assert result["status"] == "shortage"


def test_manual_policy_baseline_does_not_claim_forecast_demand():
    result = calculate_reorder(
        on_hand=2,
        free_qty=2,
        projected_at_receipt=2,
        committed_customer_outbound=0,
        forecast_demand=500,
        forecast_usable=False,
        minimum_threshold=5,
        target_stock=10,
        product_rounding=1,
    )
    assert result["forecast_demand"] == 0
    assert result["projected_after_demand"] == 2
    assert result["recommended_qty"] == 8


def test_supplier_moq_and_native_pack_uom_are_both_rounded_up():
    result = calculate_reorder(
        on_hand=2,
        free_qty=2,
        projected_at_receipt=2,
        committed_customer_outbound=0,
        forecast_demand=0,
        forecast_usable=False,
        minimum_threshold=6,
        target_stock=11,
        supplier_minimum=7,
        pack_multiple=6,
        product_rounding=1,
    )
    assert result["recommended_qty"] == 12
    assert result["target_gap"] == 9
    assert result["supplier_minimum"] == 7
    assert result["pack_multiple"] == 6


def test_no_policy_or_zero_target_never_invents_a_reorder_quantity():
    result = calculate_reorder(
        on_hand=3,
        free_qty=3,
        projected_at_receipt=3,
        committed_customer_outbound=0,
        forecast_demand=0,
        forecast_usable=False,
        minimum_threshold=None,
        target_stock=None,
    )
    assert result["status"] == "policy_missing"
    assert result["recommended_qty"] == 0
    assert not result["reorder_needed"]


def test_target_below_trigger_is_treated_as_invalid_policy():
    result = calculate_reorder(
        on_hand=2,
        free_qty=2,
        projected_at_receipt=2,
        committed_customer_outbound=0,
        forecast_demand=0,
        forecast_usable=False,
        minimum_threshold=8,
        target_stock=5,
    )
    assert result["status"] == "policy_missing"
    assert result["recommended_qty"] == 0
    assert not result["reorder_needed"]


def test_recent_delivery_signal_only_calls_inactivity_when_window_is_covered():
    today = date(2026, 10, 9)
    covered = recent_delivery_signal(
        [{"day": "2026-05-01", "delivered_units": 4}],
        today=today,
        history_start="2026-06-01",
        history_end="2026-10-08",
    )
    assert covered["available"]
    assert covered["status"] == "no_recent_deliveries"
    assert covered["last_delivery_date"] == "2026-05-01"
    short = recent_delivery_signal(
        [], today=today, history_start="2026-08-01", history_end="2026-10-08"
    )
    assert not short["available"]
