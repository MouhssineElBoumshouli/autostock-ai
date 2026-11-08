"""Order suggestions against the database: endpoint, storing a run, budget cuts, roles, shop scoping."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Branch, Forecast, OrderRun, OrderSuggestion, Organization, Part, SaleLine, StockLevel, Supplier
from app.ordering.run import last_budget, make_order_run
from tests.helpers import OWNER_PASSWORD, add_member, audit_rows, create_other_shop, logged_in_browser, member_with_own_password, run_lines, set_up_shop

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
    [line] = run_lines(browser, run)
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
    one_line = max(line["line_cost"] for line in run_lines(browser, everything))
    run = browser.post("/api/orders/suggestions", json={"budget": one_line}).json()

    by_part = {line["part_id"]: line for line in run_lines(browser, run)}
    assert by_part[str(good_margin)]["status"] == "suggested"
    assert by_part[str(cheap_margin)]["status"] == "cut_by_budget"
    assert by_part[str(cheap_margin)]["reason"].endswith("Cut to stay within the budget.")
    assert (run["kept_lines"], run["cut_lines"]) == (1, 1)
    assert run["kept_cost"] <= one_line < run["suggested_cost"]
    assert run_lines(browser, run)[0]["status"] == "suggested"  # kept lines come first



def test_the_run_has_one_total_per_supplier_and_lines_come_50_at_a_time(browser):
    set_up_shop(browser)
    shop = shop_id()
    parts = [add_part(shop, f"OIL-{n:02}", per_week=9, on_hand=0) for n in range(51)]
    alone = add_part(shop, "ALONE-1", per_week=2, on_hand=0)
    no_supplier = add_part(shop, "NONE-1", per_week=9, on_hand=0)
    with SessionLocal() as db:
        first = db.get(Part, parts[0])
        db.execute(update(Part).where(Part.id.in_(parts)).values(supplier_id=first.supplier_id))
        db.execute(update(Part).where(Part.id == no_supplier).values(supplier_id=None))
        db.commit()
        supplier_id = str(first.supplier_id)
        alone_supplier = str(db.get(Part, alone).supplier_id)

    run = browser.post("/api/orders/suggestions", json={}).json()
    by_key = {group["key"]: group for group in run["groups"]}
    assert set(by_key) == {supplier_id, alone_supplier, "none"}
    assert by_key[supplier_id]["line_count"] == by_key[supplier_id]["pending_count"] == 51
    assert by_key[supplier_id]["supplier_name"] == "Supplier OIL-00"
    assert by_key["none"]["supplier_id"] is None
    assert sum(group["total_cost"] for group in run["groups"]) == run["suggested_cost"]
    assert run["groups"][-1]["key"] == alone_supplier  # sells the least: least urgent

    path = f"/api/orders/runs/{run['id']}/lines"
    first_page = browser.get(path, params={"group": supplier_id}).json()
    second_page = browser.get(path, params={"group": supplier_id, "page": 2}).json()
    assert (first_page["total"], len(first_page["items"]), len(second_page["items"])) == (51, 50, 1)
    assert {line["part_sku"] for line in first_page["items"] + second_page["items"]} == {f"OIL-{n:02}" for n in range(51)}
    [line] = browser.get(path, params={"group": "none"}).json()["items"]
    assert line["part_sku"] == "NONE-1" and line["supplier_name"] is None


def test_lines_cut_by_the_budget_are_their_own_group_shown_last(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "LOW-MARGIN", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    add_part(shop, "HIGH-MARGIN", per_week=9, on_hand=0, unit_cost=5000, sale_price=10000)
    everything = browser.post("/api/orders/suggestions", json={}).json()
    one_line = max(line["line_cost"] for line in run_lines(browser, everything))

    run = browser.post("/api/orders/suggestions", json={"budget": one_line}).json()
    assert [group["key"] for group in run["groups"]][-1] == "didnt_fit"
    assert run["groups"][-1]["supplier_name"] is None and run["groups"][-1]["line_count"] == 1
    [cut] = browser.get(f"/api/orders/runs/{run['id']}/lines", params={"group": "didnt_fit"}).json()["items"]
    assert cut["part_sku"] == "LOW-MARGIN" and cut["status"] == "cut_by_budget"


def test_another_shop_cannot_read_the_lines_of_a_run(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    run = browser.post("/api/orders/suggestions", json={}).json()
    [group] = run["groups"]

    other = create_other_shop()
    stranger = logged_in_browser(other.email, OWNER_PASSWORD)
    page = stranger.get(f"/api/orders/runs/{run['id']}/lines", params={"group": group["key"]}).json()
    assert (page["total"], page["items"]) == (0, [])


def test_slow_seller_without_recent_sales_is_left_out_unless_out_of_stock(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "SLOW-ON-SHELF", per_week=0.2, on_hand=1, sold_recently=False)
    out = add_part(shop, "SLOW-OUT", per_week=0.2, on_hand=0, sold_recently=False)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    assert line["part_id"] == str(out)
    assert line["rule"] == "slow_out_of_stock"
    assert line["quantity"] == line["need"] >= 1  # nothing on the shelf: the full need


def test_pack_size_and_unknown_delivery_time(browser):
    set_up_shop(browser)
    add_part(shop_id(), "BOXED", per_week=9, on_hand=6, pack_size=10, delivery_days=None)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    assert line["quantity"] % 10 == 0
    assert line["delivery_days"] == 7
    assert line["delivery_source"] == "estimated"
    assert "(packs of 10)" in line["reason"]
    assert "supplier takes about 7 days (estimated)" in line["reason"]


def test_a_shop_without_forecasts_gets_an_empty_run(browser):
    set_up_shop(browser)
    run = browser.post("/api/orders/suggestions", json={}).json()
    assert run_lines(browser, run) == [] and run["history_last_day"] is None


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
    assert [line["reason"] for line in run_lines(browser, run)][0].endswith("safety cushion of 7.")
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


# A new run (made automatically after every forecast run, or by a manager clicking again) must
# keep what a person already decided on the latest run, instead of starting over from scratch.


def test_an_approved_line_still_in_a_draft_order_carries_over_unchanged(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    approved = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"}).json()

    second = browser.post("/api/orders/suggestions", json={}).json()

    [carried] = run_lines(browser, second)
    assert carried["status"] == "approved"
    assert carried["quantity"] == line["quantity"]
    assert carried["approved_quantity"] == approved["approved_quantity"]
    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["line_count"] == 1  # not a second, duplicate line on the same draft order


def test_an_edited_approved_line_keeps_its_edited_quantity(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    custom = line["quantity"] + 10
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve", "quantity": custom})

    second = browser.post("/api/orders/suggestions", json={}).json()

    [carried] = run_lines(browser, second)
    assert carried["approved_quantity"] == custom
    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["total_cost"] == custom * line["unit_cost"]


def test_an_approved_draft_line_is_never_cut_by_a_later_tighter_budget(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "OIL-1", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    add_part(shop, "OIL-2", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    first = browser.post("/api/orders/suggestions", json={}).json()
    approved_first = run_lines(browser, first)[0]
    browser.post(f"/api/orders/suggestions/{approved_first['id']}/decide", json={"decision": "approve"})

    second = browser.post("/api/orders/suggestions", json={"budget": 1}).json()  # far too small for a new line

    by_part = {line["part_id"]: line for line in run_lines(browser, second)}
    assert by_part[approved_first["part_id"]]["status"] == "approved"
    other = next(part_id for part_id in by_part if part_id != approved_first["part_id"])
    assert by_part[other]["status"] == "cut_by_budget"
    assert second["kept_lines"] == 1 and second["cut_lines"] == 1


def test_a_rejected_line_stays_rejected_when_nothing_changed(browser):
    set_up_shop(browser)
    add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "reject"})

    second = browser.post("/api/orders/suggestions", json={}).json()

    [carried] = run_lines(browser, second)
    assert carried["status"] == "rejected"
    assert browser.get("/api/orders/purchase-orders").json() == []


def test_a_rejected_line_is_suggested_again_once_the_part_runs_out(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6)
    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "reject"})
    with SessionLocal() as db:
        db.execute(update(StockLevel).where(StockLevel.part_id == part).values(quantity=0))
        db.commit()

    second = browser.post("/api/orders/suggestions", json={}).json()

    [carried] = run_lines(browser, second)
    assert carried["status"] == "suggested"


def test_automatic_runs_keep_the_owners_last_budget(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, "OIL-1", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    add_part(shop, "OIL-2", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    first = browser.post("/api/orders/suggestions", json={}).json()
    one_line_cost = max(line["line_cost"] for line in run_lines(browser, first))
    browser.post("/api/orders/suggestions", json={"budget": one_line_cost})

    with SessionLocal() as db:
        automatic = make_order_run(db, shop, last_budget(db, shop))
        db.commit()

    assert automatic.budget == one_line_cost
    assert automatic.cut_lines == 1  # the budget is still enforced, not just remembered
