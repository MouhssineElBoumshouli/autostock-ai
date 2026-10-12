"""Deterministic, explainable stock-risk and reorder calculations.

This module contains no Odoo calls. Callers pass permission-scoped Odoo quantities,
supplier terms, and forecast evidence; outputs are planning guidance, never a
purchase instruction.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import math

ALLOWED_EVALUATIONS = {"evaluated", "baseline_only", "intermittent_baseline"}
FORECAST_FRESHNESS_DAYS = 14
MIN_FORECAST_HISTORY_DAYS = 90
MIN_FORECAST_NONZERO_DAYS = 7


def _as_date(value: date | str | None) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_utc_datetime(value: datetime | str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def forecast_eligibility(
    run: dict | None,
    *,
    company_id: int,
    product_id: int,
    warehouse_id: int,
    lead_time_days: int,
    today: date,
    now: datetime,
    point_dates: list[date | str] | None = None,
    source_current: bool = True,
    freshness_days: int = FORECAST_FRESHNESS_DAYS,
) -> tuple[bool, str]:
    """Return whether one run can support this exact company/product/warehouse.

    Evaluation MAE is not thresholded here: a single chronological holdout is
    comparison evidence, not a calibrated accuracy guarantee. Review, history,
    age, identity, and coverage are hard eligibility gates.
    """
    if not run:
        return False, "No completed delivery forecast is available."
    if run.get("source_type") != "completed_deliveries":
        return False, "Synthetic forecasts are never used for real inventory recommendations."
    if (
        int(run.get("company_id") or 0) != int(company_id)
        or int(run.get("product_id") or 0) != int(product_id)
        or int(run.get("warehouse_id") or 0) != int(warehouse_id)
    ):
        return False, "The forecast does not match the selected company, product, and warehouse."
    if not source_current:
        return False, "The forecast's saved history no longer matches current Odoo deliveries and returns."
    if run.get("state") != "completed":
        return False, "The forecast run is not complete."
    evaluation = run.get("evaluation_status")
    if evaluation not in ALLOWED_EVALUATIONS:
        return False, "The forecast has no supported holdout evaluation."
    horizon = int(run.get("horizon_days") or 0)
    if horizon <= 0 or int(run.get("evaluation_days") or 0) < horizon:
        return False, "The forecast was not evaluated across its full horizon."
    if run.get("review_status") != "reviewed":
        return False, "The forecast has not been reviewed by an inventory manager."
    if int(run.get("history_days") or 0) < MIN_FORECAST_HISTORY_DAYS:
        return False, f"The forecast has fewer than {MIN_FORECAST_HISTORY_DAYS} covered history days."
    if int(run.get("nonzero_days") or 0) < MIN_FORECAST_NONZERO_DAYS:
        return False, f"The forecast has fewer than {MIN_FORECAST_NONZERO_DAYS} non-zero delivery days."
    if horizon < max(0, int(lead_time_days)):
        return False, "The forecast horizon does not cover the supplier lead time."

    cutoff = _as_utc_datetime(run.get("source_cutoff"))
    now_utc = _as_utc_datetime(now)
    if not cutoff or not now_utc:
        return False, "The forecast source cutoff is unavailable."
    age = now_utc - cutoff
    if age < timedelta(0):
        return False, "The forecast source cutoff is in the future."
    if age > timedelta(days=freshness_days):
        return False, f"The forecast source is older than {freshness_days} days."

    history_end = _as_date(run.get("history_end_date"))
    if not history_end or history_end > today or (today - history_end).days > freshness_days:
        return False, f"The latest covered delivery history must be within {freshness_days} days."

    dates = {_as_date(value) for value in point_dates or []}
    first_needed = today + timedelta(days=1)
    last_needed = today + timedelta(days=max(0, int(lead_time_days)))
    if first_needed <= last_needed:
        for offset in range((last_needed - first_needed).days + 1):
            if first_needed + timedelta(days=offset) not in dates:
                return False, "Daily forecast values do not cover every day through the supplier lead time."
    return True, "Reviewed, evaluated delivery history covers this lead-time window."


def _ceil_to_step(value: float, step: float) -> float:
    if not math.isfinite(value) or value <= 0:
        return 0.0
    if not math.isfinite(step) or step <= 0:
        return value
    quantity = Decimal(str(value))
    increment = Decimal(str(step))
    multiples = (quantity / increment).to_integral_value(rounding=ROUND_CEILING)
    return float(multiples * increment)


def calculate_reorder(
    *,
    on_hand: float,
    free_qty: float,
    projected_at_receipt: float,
    committed_customer_outbound: float,
    forecast_demand: float,
    forecast_usable: bool,
    minimum_threshold: float | None,
    target_stock: float | None,
    supplier_minimum: float = 0.0,
    pack_multiple: float = 0.0,
    product_rounding: float = 1.0,
) -> dict:
    """Calculate a trigger-based top-up in the product's inventory unit.

    Odoo's projected quantity already contains confirmed outgoing moves and does
    not subtract reservations. Forecast deliveries overlap known sale-linked
    outbound moves, so only the uncommitted remainder is deducted.
    """
    forecast_demand = max(0.0, float(forecast_demand or 0.0)) if forecast_usable else 0.0
    committed = max(0.0, float(committed_customer_outbound or 0.0))
    additional_demand = max(0.0, forecast_demand - committed) if forecast_usable else 0.0
    expected = float(projected_at_receipt or 0.0) - additional_demand
    minimum = None if minimum_threshold is None else max(0.0, float(minimum_threshold))
    target = None if target_stock is None else max(0.0, float(target_stock))

    policy_valid = minimum is not None and target is not None and target >= minimum
    if float(on_hand or 0.0) <= 0:
        status = "out"
    elif not policy_valid:
        status = "policy_missing"
    elif expected < minimum:
        status = "shortage"
    elif float(free_qty or 0.0) <= minimum:
        status = "low"
    elif target > 0 and expected > target:
        status = "overstock"
    else:
        status = "healthy"

    recommended = 0.0
    reorder_needed = policy_valid and expected < minimum
    target_gap = max(0.0, target - expected) if target is not None else 0.0
    if reorder_needed:
        raw = max(target_gap, max(0.0, float(supplier_minimum or 0.0)))
        recommended = _ceil_to_step(raw, pack_multiple or product_rounding)

    return {
        "status": status,
        "projected_after_demand": expected,
        "forecast_demand": forecast_demand,
        "committed_customer_outbound": committed,
        "additional_forecast_demand": additional_demand,
        "reorder_needed": reorder_needed,
        "target_gap": target_gap,
        "recommended_qty": recommended,
        "minimum_threshold": minimum,
        "target_stock": target,
        "supplier_minimum": max(0.0, float(supplier_minimum or 0.0)),
        "pack_multiple": max(0.0, float(pack_multiple or 0.0)),
    }


def recent_delivery_signal(
    observations: list[dict], *, today: date, history_start: date | str | None,
    history_end: date | str | None, last_delivery_date: date | str | None = None,
    window_days: int = 90,
) -> dict:
    """Report dated delivery inactivity only when the full window is covered."""
    start = _as_date(history_start)
    end = _as_date(history_end)
    window_start = today - timedelta(days=window_days - 1)
    if not start or not end or start > window_start or end < today - timedelta(days=14):
        return {"available": False, "status": "insufficient_coverage", "window_days": window_days}
    deliveries = [
        _as_date(row.get("day"))
        for row in observations
        if _as_date(row.get("day")) and float(row.get("delivered_units") or row.get("units") or 0) > 0
    ]
    recent = [day for day in deliveries if window_start <= day <= today]
    if recent:
        return {
            "available": True,
            "status": "recent_delivery",
            "window_days": window_days,
            "last_delivery_date": max(recent).isoformat(),
        }
    older = [day for day in deliveries if day < window_start]
    last_delivery = _as_date(last_delivery_date) or (max(older) if older else None)
    return {
        "available": True,
        "status": "no_recent_deliveries",
        "window_days": window_days,
        "last_delivery_date": last_delivery.isoformat() if last_delivery else None,
    }
