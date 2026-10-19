"""Forecast runs against the database: storing, shop scoping, endpoints, and the run after a sales import."""

import uuid
from datetime import date, timedelta
from time import perf_counter

import numpy as np
from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.forecast import run as forecast_run
from app.forecast.engine import HORIZONS
from app.forecast.run import load_demand, run_forecasts, run_forecasts_in_background
from app.models import Branch, Forecast, ForecastRun, Organization, Part, SaleLine, StockOut
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, set_up_shop
from tests.import_helpers import import_parts, import_sales

LAST_DAY = date(2026, 9, 30)
DAYS = 200


def add_sales(organization_id: uuid.UUID, sku: str, per_day: int = 2, active: bool = True) -> tuple[uuid.UUID, uuid.UUID]:
    """A part that sold `per_day` every day for DAYS days, ending on LAST_DAY, in the shop's first branch."""
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        part = Part(organization_id=organization_id, sku=sku, name=f"Part {sku}", is_active=active)
        db.add(part)
        db.flush()
        for i in range(DAYS):
            day = LAST_DAY - timedelta(days=i)
            db.add(SaleLine(organization_id=organization_id, sold_on=day, part_id=part.id, branch_id=branch.id, quantity=per_day))
        db.commit()
        return part.id, branch.id


def shop_id() -> uuid.UUID:
    with SessionLocal() as db:
        return db.scalar(select(Organization.id).where(Organization.name == "Atlas Parts"))


def forecasts_of(organization_id: uuid.UUID) -> list[Forecast]:
    with SessionLocal() as db:
        return list(db.scalars(select(Forecast).where(Forecast.organization_id == organization_id)))


def run_now(organization_id: uuid.UUID) -> ForecastRun:
    with SessionLocal() as db:
        run = run_forecasts(db, organization_id, "manual")
        db.commit()
        return run


def test_a_run_stores_one_forecast_per_part_branch_and_horizon(browser):
    set_up_shop(browser)
    shop = shop_id()
    part_id, branch_id = add_sales(shop, "OIL-1", per_day=2)
    add_sales(shop, "OLD-1", active=False)

    run = run_now(shop)

    assert run.status == "done" and run.series_count == 1 and run.history_last_day == LAST_DAY
    saved = sorted(forecasts_of(shop), key=lambda f: f.horizon_days)
    assert [f.horizon_days for f in saved] == list(HORIZONS)
    for forecast in saved:
        assert (forecast.part_id, forecast.branch_id) == (part_id, branch_id)
        assert forecast.quantity == 2 * forecast.horizon_days  # sold exactly 2 a day
        assert forecast.low <= forecast.quantity <= forecast.high
        assert forecast.demand_type == "smooth" and forecast.method and forecast.reason
        assert forecast.history_last_day == LAST_DAY and forecast.backtest_windows > 0


def test_running_again_replaces_the_forecasts(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_sales(shop, "OIL-1")
    run_now(shop)
    run_now(shop)
    assert len(forecasts_of(shop)) == len(HORIZONS)


def test_stock_out_days_are_read_as_unknown(browser):
    set_up_shop(browser)
    shop = shop_id()
    part_id, branch_id = add_sales(shop, "OIL-1")
    with SessionLocal() as db:
        db.add(StockOut(organization_id=shop, part_id=part_id, branch_id=branch_id,
                        first_day=LAST_DAY - timedelta(days=9), last_day=LAST_DAY - timedelta(days=5)))
        db.commit()
        demand = load_demand(db, shop).demand[0]
    assert np.isnan(demand[-10:-5]).all() and not np.isnan(demand[:-10]).any() and not np.isnan(demand[-5:]).any()


def test_a_shop_without_sales_gets_an_empty_run(browser):
    set_up_shop(browser)
    run = run_now(shop_id())
    assert run.status == "done" and run.series_count == 0 and run.history_last_day is None


def test_each_shop_only_touches_its_own_forecasts(browser):
    set_up_shop(browser)
    shop = shop_id()
    other = create_other_shop().organization_id
    add_sales(shop, "OIL-1")
    other_part, _ = add_sales(other, "OTHER-1")
    run_now(other)
    run_now(shop)
    assert {f.part_id for f in forecasts_of(other)} == {other_part}
    assert len(forecasts_of(shop)) == len(HORIZONS)


def test_manager_runs_forecasts_on_demand_and_anyone_sees_the_latest_run(browser):
    set_up_shop(browser)
    add_sales(shop_id(), "OIL-1")
    assert browser.get("/api/forecasts/runs/latest").json() is None

    response = browser.post("/api/forecasts/run")

    assert response.status_code == 202, response.text
    latest = browser.get("/api/forecasts/runs/latest").json()
    assert latest["status"] == "done" and latest["trigger"] == "manual" and latest["series_count"] == 1
    assert latest["seconds"] >= 0 and latest["history_last_day"] == LAST_DAY.isoformat()
    assert len(audit_rows("forecast.requested")) == 1

    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    assert staff.post("/api/forecasts/run").status_code == 403
    assert staff.get("/api/forecasts/runs/latest").status_code == 200


def test_logged_out_people_cannot_run_forecasts(browser):
    set_up_shop(browser)
    browser.post("/api/auth/logout")
    assert browser.post("/api/forecasts/run").status_code == 401


def test_a_sales_import_remakes_the_forecasts(browser):
    set_up_shop(browser)
    import_parts(browser)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ForecastRun)) == 0  # parts alone: no run

    import_sales(browser)

    latest = browser.get("/api/forecasts/runs/latest").json()
    assert latest["trigger"] == "sales_import" and latest["status"] == "done"
    assert len(forecasts_of(shop_id())) == latest["series_count"] * len(HORIZONS) > 0


def test_a_failed_run_is_recorded(browser, monkeypatch):
    set_up_shop(browser)
    add_sales(shop_id(), "OIL-1")

    def broken(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(forecast_run, "forecast_all", broken)
    run_forecasts_in_background(shop_id(), "manual")
    assert browser.get("/api/forecasts/runs/latest").json()["status"] == "failed"


def test_merging_a_branch_moves_its_stock_outs_and_drops_its_forecasts(browser):
    set_up_shop(browser)
    shop = shop_id()
    part_id, first_branch = add_sales(shop, "OIL-1")
    with SessionLocal() as db:
        second = Branch(organization_id=shop, name="Rabat")
        db.add(second)
        db.add(StockOut(organization_id=shop, part_id=part_id, branch_id=first_branch, first_day=LAST_DAY, last_day=LAST_DAY))
        db.commit()
    run_now(shop)

    assert browser.post(f"/api/branches/{first_branch}/merge", json={"into": str(second.id)}).status_code == 204

    assert forecasts_of(shop) == []
    with SessionLocal() as db:
        assert db.scalar(select(StockOut.branch_id)) == second.id


def test_a_full_demo_shop_is_forecast_in_under_2_minutes():
    with SessionLocal() as db:
        shop = create_demo_shop(db, LAST_DAY)
        db.commit()
    started = perf_counter()
    run = run_now(shop.id)
    seconds = perf_counter() - started
    print(f"Forecast run for {run.series_count} part-branch pairs: {seconds:.1f} s")
    assert run.series_count > 500 and seconds < 120
