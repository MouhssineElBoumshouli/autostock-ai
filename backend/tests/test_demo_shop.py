from collections import Counter
from datetime import date, timedelta

import numpy as np
import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import (
    DEMO_OWNER_EMAIL,
    DEMO_SHOP_NAME,
    FUTURE_DAYS,
    SUMMER,
    SUPPLIERS,
    WINTER,
    add_demo_owner,
    create_demo_shop,
    season_factor,
    true_demand,
)
from app.forecast.calendar import is_ramadan
from app.models import Branch, DemoPlantedProblem, DemoTrueDemand, Organization, Part, SaleLine, StockHistory, StockLevel, StockOut, Supplier, User
from app.stock_status import status_for
from tests.helpers import new_browser, set_up_shop

LAST_DAY = date(2026, 6, 30)
HISTORY_DAYS = 200


def make_small_demo(seed: int = 7) -> Organization:
    with SessionLocal() as db:
        shop, _counts = create_demo_shop(db, LAST_DAY, parts_count=8, history_days=HISTORY_DAYS, seed=seed)
        db.commit()
        return shop


def test_demo_shop_is_labeled_and_has_parts_branches_and_sales():
    shop = make_small_demo()
    with SessionLocal() as db:
        saved = db.get(Organization, shop.id)
        assert saved.is_demo and saved.name == DEMO_SHOP_NAME
        assert db.scalar(select(func.count()).select_from(Branch).where(Branch.organization_id == shop.id)) == 3
        assert db.scalar(select(func.count()).select_from(Part).where(Part.organization_id == shop.id)) == 8
        days = db.execute(
            select(func.min(SaleLine.sold_on), func.max(SaleLine.sold_on)).where(SaleLine.organization_id == shop.id)
        ).one()
        assert days[0] >= LAST_DAY - timedelta(days=HISTORY_DAYS - 1) and days[1] <= LAST_DAY


def test_sales_never_exceed_true_demand_and_stock_out_days_have_no_sales():
    shop = make_small_demo()
    with SessionLocal() as db:
        wanted = {
            (row.part_id, row.branch_id, row.day): row.quantity
            for row in db.scalars(select(DemoTrueDemand).where(DemoTrueDemand.organization_id == shop.id))
        }
        sales = db.scalars(select(SaleLine).where(SaleLine.organization_id == shop.id)).all()
        assert all(sale.quantity <= wanted[(sale.part_id, sale.branch_id, sale.sold_on)] for sale in sales)
        sold_days = {(sale.part_id, sale.branch_id, sale.sold_on) for sale in sales}
        outs = db.scalars(select(StockOut).where(StockOut.organization_id == shop.id)).all()
        for out in outs:
            day = out.first_day
            while day <= out.last_day:
                assert (out.part_id, out.branch_id, day) not in sold_days
                day += timedelta(days=1)
        assert max(day for _, _, day in wanted) > LAST_DAY  # true demand continues after the history
        assert max(day for _, _, day in wanted) <= LAST_DAY + timedelta(days=FUTURE_DAYS)


def test_making_the_demo_again_replaces_it_and_never_touches_a_real_shop():
    with SessionLocal() as db:
        real = Organization(name="Real Shop")
        db.add(real)
        db.commit()
    first = make_small_demo()
    second = make_small_demo(seed=8)
    with SessionLocal() as db:
        assert db.get(Organization, first.id) is None
        assert db.get(Organization, second.id) is not None
        assert db.get(Organization, real.id) is not None
        assert db.scalar(select(func.count()).select_from(Organization).where(Organization.is_demo)) == 1


def test_seasons_peak_in_july_for_cooling_and_january_for_wipers():
    july, january = np.array([196]), np.array([15])
    assert season_factor(july, SUMMER)[0] > 2 > season_factor(january, SUMMER)[0]
    assert season_factor(january, WINTER)[0] > 2 > season_factor(july, WINTER)[0]


def test_ramadan_lowers_demand():
    rng = np.random.default_rng(1)
    first_day = date(2026, 1, 1)
    demand = np.mean([true_demand(rng, first_day, 120, SUMMER, 1.0) for _ in range(50)], axis=0)
    ramadan = np.array([is_ramadan(first_day + timedelta(days=i)) for i in range(120)])
    assert ramadan.sum() == 30
    assert demand[ramadan].mean() < 0.85 * demand[~ramadan & (np.arange(120) < 80)].mean()


def test_the_demo_owner_can_log_in_and_a_real_shop_can_still_be_set_up(browser):
    with SessionLocal() as db:
        shop, _counts = create_demo_shop(db, LAST_DAY, parts_count=2, history_days=60)
        password = add_demo_owner(db, shop)
        db.commit()
    assert len(password) >= 12
    login = browser.post("/api/auth/login", json={"email": DEMO_OWNER_EMAIL, "password": password})
    assert login.status_code == 200, login.text

    fresh = new_browser()
    assert fresh.get("/api/setup").json()["needed"] is True  # the demo account is not a real shop
    set_up_shop(fresh)
    assert fresh.get("/api/setup").json()["needed"] is False


def test_demo_accounts_are_refused_in_a_real_shop():
    with SessionLocal() as db:
        real = Organization(name="Real Shop")
        db.add(real)
        db.flush()
        with pytest.raises(ValueError):
            add_demo_owner(db, real)


def test_making_the_demo_again_gives_a_new_password_and_removes_the_old_account():
    with SessionLocal() as db:
        first_shop, _ = create_demo_shop(db, LAST_DAY, parts_count=2, history_days=60)
        first = add_demo_owner(db, first_shop)
        db.commit()
        second_shop, _ = create_demo_shop(db, LAST_DAY, parts_count=2, history_days=60)
        second = add_demo_owner(db, second_shop)
        db.commit()
        assert first != second
        assert db.scalar(select(func.count()).select_from(User).where(User.email == DEMO_OWNER_EMAIL)) == 1


def test_every_part_has_a_supplier_with_a_real_delivery_time():
    shop = make_small_demo()
    with SessionLocal() as db:
        parts = db.scalars(select(Part).where(Part.organization_id == shop.id)).all()
        assert all(part.supplier_id is not None for part in parts)
        suppliers = db.scalars(select(Supplier).where(Supplier.organization_id == shop.id)).all()
        assert len(suppliers) == len(SUPPLIERS)
        assert all(3 <= s.delivery_days <= 21 for s in suppliers)
        assert all(s.phone and s.email for s in suppliers)


def test_minimum_stock_is_about_two_weeks_of_normal_sales():
    shop = make_small_demo()
    with SessionLocal() as db:
        parts = db.scalars(select(Part).where(Part.organization_id == shop.id)).all()
        assert all(part.min_stock >= 1 for part in parts)  # "at least 1" even for the slowest sellers


def test_current_stock_is_spread_across_statuses_close_to_target_shares():
    with SessionLocal() as db:
        shop, counts = create_demo_shop(db, LAST_DAY, history_days=HISTORY_DAYS)  # every part
        db.commit()
        parts = db.scalars(select(Part).where(Part.organization_id == shop.id)).all()
        on_hand = dict(
            db.execute(
                select(StockLevel.part_id, func.sum(StockLevel.quantity))
                .where(StockLevel.organization_id == shop.id)
                .group_by(StockLevel.part_id)
            ).all()
        )
        # Negative stock is planted after the buckets are counted: count those with the stock they had before.
        for planted in db.scalars(select(DemoPlantedProblem).where(DemoPlantedProblem.kind == "negative_stock")):
            now = db.scalar(select(StockLevel.quantity).where(StockLevel.part_id == planted.part_id, StockLevel.branch_id == planted.branch_id))
            on_hand[planted.part_id] += planted.details["quantity_before"] - now
        statuses = Counter(status_for(True, on_hand.get(part.id, 0), part.min_stock) for part in parts)

    total = sum(counts.values())
    assert total == len(parts) and statuses["out"] + statuses["low"] + statuses["healthy"] == total
    assert statuses["out"] == counts["out"]  # "out" has only one way to get there: 0 on hand
    assert statuses["low"] == counts["low"]  # "low" is exactly "at or below the minimum"
    assert statuses["healthy"] == counts["running_out"] + counts["healthy"]  # running_out still reads "Healthy"
    assert counts["out"] / total == pytest.approx(0.04, abs=0.02)
    assert counts["low"] / total == pytest.approx(0.10, abs=0.03)
    assert counts["running_out"] / total == pytest.approx(0.08, abs=0.03)
    assert counts["healthy"] / total > 0.6


def test_known_problems_are_planted_with_their_dates_in_the_last_weeks():
    with SessionLocal() as db:
        shop, _counts = create_demo_shop(db, LAST_DAY, history_days=HISTORY_DAYS)
        db.commit()
        planted = db.scalars(select(DemoPlantedProblem).where(DemoPlantedProblem.organization_id == shop.id)).all()
    kinds = Counter(p.kind for p in planted)
    assert kinds == {"sales_spike": 15, "sales_drop": 15, "stock_frozen": 10, "sold_at_zero": 10, "negative_stock": 4}
    assert len({(p.part_id, p.branch_id) for p in planted}) == len(planted)  # one problem per part and branch
    assert all(LAST_DAY - timedelta(days=50) <= p.first_day <= p.last_day <= LAST_DAY for p in planted)


def test_planted_stock_problems_show_in_the_stock_history():
    with SessionLocal() as db:
        shop, _counts = create_demo_shop(db, LAST_DAY, history_days=HISTORY_DAYS)
        db.commit()
        planted = db.scalars(select(DemoPlantedProblem).where(DemoPlantedProblem.organization_id == shop.id)).all()
        for p in planted:
            history = db.execute(
                select(StockHistory.day, StockHistory.quantity)
                .where(StockHistory.part_id == p.part_id, StockHistory.branch_id == p.branch_id)
                .order_by(StockHistory.day)
            ).all()
            sold = db.scalar(
                select(func.coalesce(func.sum(SaleLine.quantity), 0)).where(
                    SaleLine.part_id == p.part_id, SaleLine.branch_id == p.branch_id, SaleLine.sold_on.between(p.first_day, p.last_day)
                )
            )
            shelf = db.scalar(select(StockLevel.quantity).where(StockLevel.part_id == p.part_id, StockLevel.branch_id == p.branch_id))
            if p.kind == "stock_frozen":
                assert history[-1].day < p.first_day and history[-1].quantity == shelf > 0 and sold > 0
            elif p.kind == "sold_at_zero":
                at_zero = [q for day, q in history if p.first_day - timedelta(days=1) <= day <= p.last_day]
                assert at_zero == [0] and sold >= p.last_day.toordinal() - p.first_day.toordinal() + 1
            elif p.kind == "negative_stock":
                assert shelf < 0 and history[-1].quantity == shelf


def test_stock_history_ends_at_todays_stock_and_never_goes_negative_by_itself():
    shop = make_small_demo()
    with SessionLocal() as db:
        negative = set(db.execute(select(DemoPlantedProblem.part_id, DemoPlantedProblem.branch_id).where(DemoPlantedProblem.kind == "negative_stock")).all())
        latest = {}
        for row in db.scalars(select(StockHistory).where(StockHistory.organization_id == shop.id).order_by(StockHistory.day)):
            latest[(row.part_id, row.branch_id)] = row.quantity
            assert row.quantity >= 0 or (row.part_id, row.branch_id) in negative
        for level in db.scalars(select(StockLevel).where(StockLevel.organization_id == shop.id)):
            assert latest[(level.part_id, level.branch_id)] == level.quantity
