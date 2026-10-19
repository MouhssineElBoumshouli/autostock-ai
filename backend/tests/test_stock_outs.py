from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Branch, Organization, Part, StockLevel, StockOut
from app.stock_outs import record_all_stock_outs, record_stock_outs
from tests.helpers import set_up_shop
from tests.import_helpers import import_parts

TODAY = date(2026, 10, 19)


def shop_with_stock(name: str, quantities: dict[str, int], is_demo: bool = False, inactive: tuple = ()) -> tuple:
    with SessionLocal() as db:
        shop = Organization(name=name, is_demo=is_demo)
        db.add(shop)
        db.flush()
        branch = Branch(organization_id=shop.id, name="Main")
        db.add(branch)
        db.flush()
        parts = {}
        for sku, quantity in quantities.items():
            part = Part(organization_id=shop.id, sku=sku, name=sku, is_active=sku not in inactive)
            db.add(part)
            db.flush()
            db.add(StockLevel(organization_id=shop.id, part_id=part.id, branch_id=branch.id, quantity=quantity))
            parts[sku] = part.id
        db.commit()
        return shop.id, parts


def record(shop_id, day: date) -> None:
    with SessionLocal() as db:
        record_stock_outs(db, shop_id, day)
        db.commit()


def periods(shop_id) -> list[tuple]:
    with SessionLocal() as db:
        outs = db.scalars(select(StockOut).where(StockOut.organization_id == shop_id).order_by(StockOut.first_day))
        return [(out.part_id, out.first_day, out.last_day) for out in outs]


def set_stock(part_id, quantity: int) -> None:
    with SessionLocal() as db:
        db.scalar(select(StockLevel).where(StockLevel.part_id == part_id)).quantity = quantity
        db.commit()


def test_only_active_parts_at_zero_stock_are_saved_once_per_day():
    shop, parts = shop_with_stock("Real", {"EMPTY": 0, "FULL": 5, "OLD": 0}, inactive=("OLD",))
    record(shop, TODAY)
    record(shop, TODAY)  # checked again the same day: nothing new
    assert periods(shop) == [(parts["EMPTY"], TODAY, TODAY)]


def test_still_empty_the_next_day_extends_the_period_and_a_refill_ends_it():
    shop, parts = shop_with_stock("Real", {"EMPTY": 0})
    record(shop, TODAY)
    record(shop, TODAY + timedelta(days=1))
    assert periods(shop) == [(parts["EMPTY"], TODAY, TODAY + timedelta(days=1))]

    set_stock(parts["EMPTY"], 3)
    record(shop, TODAY + timedelta(days=2))
    set_stock(parts["EMPTY"], 0)
    record(shop, TODAY + timedelta(days=3))
    assert periods(shop) == [
        (parts["EMPTY"], TODAY, TODAY + timedelta(days=1)),
        (parts["EMPTY"], TODAY + timedelta(days=3), TODAY + timedelta(days=3)),
    ]


def test_the_daily_check_covers_every_real_shop_but_never_the_demo():
    real, _ = shop_with_stock("Real", {"A": 0})
    other, _ = shop_with_stock("Other", {"B": 0})
    demo, _ = shop_with_stock("Demo", {"C": 0}, is_demo=True)
    record_all_stock_outs(TODAY)
    assert len(periods(real)) == 1 and len(periods(other)) == 1 and periods(demo) == []


def test_a_parts_import_saves_todays_stock_outs(browser):
    set_up_shop(browser)
    import_parts(browser, "parts_en_clean.csv")
    with SessionLocal() as db:
        empty = set(db.scalars(select(StockLevel.part_id).where(StockLevel.quantity <= 0)))
        saved = set(db.scalars(select(StockOut.part_id).where(StockOut.first_day == date.today())))
    assert empty and saved == empty
