"""Order suggestions against the database: endpoint, storing a run, budget cuts, roles, shop scoping."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Branch, Forecast, OrderRun, OrderSuggestion, Organization, Part, SaleLine, StockLevel, Supplier
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, set_up_shop

LAST_DAY = date(2026, 9, 30)


def shop_id() -> uuid.UUID:
    with SessionLocal() as db:
        return db.scalar(select(Organization.id).where(Organization.name == "Atlas Parts"))


def add_part(organization_id: uuid.UUID, sku: str, per_week: float, on_hand: int, delivery_days: int | None = 14,
             pack_size: int = 1, unit_cost: int = 7000, sale_price: int = 10000, sold_recently: bool = True) -> uuid.UUID:
    """A part with a 30-day forecast of `per_week` a week (range +8), stock and recent sales."""
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        supplier = Supplier(organization_id=organization_id, name=f"Supplier {sku}", delivery_days=delivery_days)
        db.add(supplier)
        db.flush()
        part = Part(organization_id=organization_id, sku=sku, name=f"Part {sku}", supplier_id=supplier.id,
                    pack_size=pack_size, unit_cost=unit_cost, sale_price=sale_price)
        db.add(part)
        db.flush()
        quantity = per_week * 30 / 7
        db.add(Forecast(organization_id=organization_id, part_id=part.id, branch_id=branch.id, horizon_days=30,
                        history_last_day=LAST_DAY, demand_type="smooth", method="four_week_average", quantity=quantity,
                        low=max(quantity - 8, 0), high=quantity + 8, backtest_windows=12, reason="test"))
        db.add(StockLevel(organization_id=organization_id, part_id=part.id, branch_id=branch.id, quantity=on_hand))
        sold_on = LAST_DAY - timedelta(days=3 if sold_recently else 60)
        db.add(SaleLine(organization_id=organization_id, sold_on=sold_on, part_id=part.id, branch_id=branch.id, quantity=2))
        db.commit()
        return part.id


def test_manager_gets_one_line_per_part_to_order_with_its_reason(browser):
    set_up_shop(browser)
    shop = shop_id()
    oil = add_part(shop, "OIL-1", per_week=9, on_hand=6)
    add_part(shop, "FULL-1", per_week=1, on_hand=50)  # plenty on the shelf: no line

    response = browser.post("/api/orders/suggestions", json={})
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["history_last_day"] == "2026-09-30"
    assert run["kept_lines"] == 1 and run["cut_lines"] == 0
    [line] = run["lines"]
    assert line["part_id"] == str(oil)
    assert line["status"] == "suggested"
    assert line["days_covered"] == 21
    assert line["expected"] == 27.0  # 9 a week for 3 weeks
    assert line["quantity"] == line["need"] - 6
    assert line["line_cost"] == line["quantity"] * 7000
    assert line["reason"].startswith("Sells about 9 a week, supplier takes 14 days, 6 left: order ")
    assert line["sold_last_90_days"] >= 0  # the website rebuilds the reason in French or Arabic from these numbers
    assert run["suggested_cost"] == run["kept_cost"] == line["line_cost"]


def test_a_run_costing_more_than_21_million_dirhams_is_saved(browser):
    set_up_shop(browser)
    shop = shop_id()
    for n in range(3):  # each line about 9 million MAD: 3 x 18,000 pieces at 500 MAD
        add_part(shop, f"BIG-{n}", per_week=6000, on_hand=0, unit_cost=50000)

    response = browser.post("/api/orders/suggestions", json={})
    assert response.status_code == 201, response.text
    assert response.json()["suggested_cost"] > 2**31  # more than a plain integer of centimes holds


def test_every_run_is_stored_and_the_latest_one_is_read_back(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    first = browser.post("/api/orders/suggestions", json={}).json()
    second = browser.post("/api/orders/suggestions", json={"budget": 0}).json()

    latest = browser.get("/api/orders/suggestions/latest").json()
    assert latest["id"] == second["id"] != first["id"]
    with SessionLocal() as db:
        assert len(db.scalars(select(OrderRun)).all()) == 2
        assert len(db.scalars(select(OrderSuggestion)).all()) == 2
    [row] = audit_rows("order_suggestions.created")[-1:]
    assert row.after["budget"] == 0


def test_nothing_is_ordered_automatically(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    browser.post("/api/orders/suggestions", json={})
    with SessionLocal() as db:
        level = db.scalar(select(StockLevel).where(StockLevel.part_id == part))
        assert level.quantity == 6  # suggestions change no stock


def test_budget_keeps_the_most_valuable_lines_and_says_which_were_cut(browser):
    set_up_shop(browser)
    shop = shop_id()
    cheap_margin = add_part(shop, "LOW-MARGIN", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    good_margin = add_part(shop, "HIGH-MARGIN", per_week=9, on_hand=0, unit_cost=5000, sale_price=10000)

    everything = browser.post("/api/orders/suggestions", json={}).json()
    one_line = max(line["line_cost"] for line in everything["lines"])
    run = browser.post("/api/orders/suggestions", json={"budget": one_line}).json()

    by_part = {line["part_id"]: line for line in run["lines"]}
    assert by_part[str(good_margin)]["status"] == "suggested"
    assert by_part[str(cheap_margin)]["status"] == "cut_by_budget"
    assert by_part[str(cheap_margin)]["reason"].endswith("Cut to stay within the budget.")
    assert (run["kept_lines"], run["cut_lines"]) == (1, 1)
    assert run["kept_cost"] <= one_line < run["suggested_cost"]
    assert run["lines"][0]["status"] == "suggested"  # kept lines come first


def test_slow_seller_without_recent_sales_is_left_out_unless_out_of_stock(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "SLOW-ON-SHELF", per_week=0.2, on_hand=1, sold_recently=False)
    out = add_part(shop, "SLOW-OUT", per_week=0.2, on_hand=0, sold_recently=False)
    [line] = browser.post("/api/orders/suggestions", json={}).json()["lines"]
    assert line["part_id"] == str(out)
    assert line["rule"] == "slow_out_of_stock"
    assert line["quantity"] == line["need"] >= 1  # nothing on the shelf: the full need


def test_pack_size_and_unknown_delivery_time(browser):
    set_up_shop(browser)
    add_part(shop_id(), "BOXED", per_week=9, on_hand=6, pack_size=10, delivery_days=None)
    [line] = browser.post("/api/orders/suggestions", json={}).json()["lines"]
    assert line["quantity"] % 10 == 0
    assert line["delivery_days"] == 7
    assert "(packs of 10)" in line["reason"]
    assert "7 days assumed" in line["reason"]


def test_a_shop_without_forecasts_gets_an_empty_run(browser):
    set_up_shop(browser)
    run = browser.post("/api/orders/suggestions", json={}).json()
    assert run["lines"] == [] and run["history_last_day"] is None


def test_negative_budget_is_refused(browser):
    set_up_shop(browser)
    assert browser.post("/api/orders/suggestions", json={"budget": -1}).status_code == 422


def test_staff_can_view_but_not_ask_for_suggestions(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    browser.post("/api/orders/suggestions", json={})
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    assert staff.post("/api/orders/suggestions", json={}).status_code == 403
    assert staff.get("/api/orders/suggestions/latest").status_code == 200


def test_each_shop_only_sees_its_own_suggestions(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    other = create_other_shop()
    add_part(other.organization_id, "OTHER-1", per_week=9, on_hand=0)
    run = browser.post("/api/orders/suggestions", json={}).json()
    assert [line["reason"] for line in run["lines"]][0].endswith("safety cushion of 7.")
    with SessionLocal() as db:
        parts = {line.part_id for line in db.scalars(select(OrderSuggestion))}
        assert db.scalars(select(Part.sku).where(Part.id.in_(parts))).all() == ["OIL-1"]


def test_merging_a_supplier_keeps_its_past_suggestions(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "OIL-1", per_week=9, on_hand=6)
    add_part(shop, "OIL-2", per_week=9, on_hand=6)
    browser.post("/api/orders/suggestions", json={})
    with SessionLocal() as db:
        source, target = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    assert browser.post(f"/api/suppliers/{source.id}/merge", json={"into": str(target.id)}).status_code == 204
    with SessionLocal() as db:
        assert {line.supplier_id for line in db.scalars(select(OrderSuggestion))} == {target.id}
