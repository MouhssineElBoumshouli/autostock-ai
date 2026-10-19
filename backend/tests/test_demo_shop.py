from datetime import date, timedelta

import numpy as np
from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import (
    DEMO_SHOP_NAME,
    FUTURE_DAYS,
    SUMMER,
    WINTER,
    create_demo_shop,
    season_factor,
    true_demand,
)
from app.forecast.calendar import is_ramadan
from app.models import Branch, DemoTrueDemand, Organization, Part, SaleLine, StockOut

LAST_DAY = date(2026, 6, 30)
HISTORY_DAYS = 200


def make_small_demo(seed: int = 7) -> Organization:
    with SessionLocal() as db:
        shop = create_demo_shop(db, LAST_DAY, parts_count=8, history_days=HISTORY_DAYS, seed=seed)
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
