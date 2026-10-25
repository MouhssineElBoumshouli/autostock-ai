"""The Today page: alerts by group, what's pending to order, late deliveries, and weekly sales."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Alert, Branch, Part, PurchaseOrder, SaleLine
from tests.helpers import add_member, create_other_shop, member_with_own_password, set_up_shop
from tests.test_orders import add_part, shop_id
from tests.test_purchase_orders import one_suggestion

LAST_DAY = date(2026, 9, 30)


def add_alert(organization_id: uuid.UUID, kind: str, money_at_stake: int, status: str = "open") -> uuid.UUID:
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        part = Part(organization_id=organization_id, sku=f"SKU-{uuid.uuid4().hex[:6]}", name=f"Part worth {money_at_stake}",
                    unit_cost=1000)
        db.add(part)
        db.flush()
        alert = Alert(
            organization_id=organization_id, part_id=part.id, branch_id=branch.id, kind=kind,
            sentence="Something unusual.", numbers={}, money_at_stake=money_at_stake,
            started_on=LAST_DAY, raised_on=LAST_DAY, status=status,
        )
        db.add(alert)
        db.commit()
        return alert.id


def add_sale(organization_id: uuid.UUID, sold_on: date, quantity: int, sku: str = "SALE-PART") -> uuid.UUID:
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        part = db.scalar(select(Part).where(Part.organization_id == organization_id, Part.sku == sku))
        if part is None:
            part = Part(organization_id=organization_id, sku=sku, name=sku, unit_cost=1000)
            db.add(part)
            db.flush()
        db.add(SaleLine(organization_id=organization_id, sold_on=sold_on, part_id=part.id, branch_id=branch.id, quantity=quantity))
        db.commit()
        return part.id


def test_alerts_are_split_by_group_and_capped_but_counted_in_full(browser):
    set_up_shop(browser)
    shop = shop_id()
    for money in (10, 20, 30, 40, 50, 60):
        add_alert(shop, "negative_stock", money)
    add_alert(shop, "sales_spike", 5)
    add_alert(shop, "sales_drop", 999)
    add_alert(shop, "negative_stock", 1000, status="looked_at")  # reviewed: not counted

    data = browser.get("/api/today").json()
    assert data["needs_action_total"] == 6
    assert len(data["needs_action"]) == 5
    # Most money at stake first; the smallest (worth 10) is left off since only 5 are shown.
    assert [a["part_name"] for a in data["needs_action"]] == [f"Part worth {m}" for m in (60, 50, 40, 30, 20)]
    assert data["worth_a_look_total"] == 2
    assert {a["kind"] for a in data["worth_a_look"]} == {"sales_spike", "sales_drop"}


def test_to_order_counts_only_pending_lines(browser):
    set_up_shop(browser)
    assert browser.get("/api/today").json()["to_order"] is None  # no run yet

    shop = shop_id()
    add_part(shop, sku="OIL-1", per_week=9, on_hand=6)
    add_part(shop, sku="OIL-2", per_week=5, on_hand=1)
    run = browser.post("/api/orders/suggestions", json={}).json()
    line_a, line_b = run["lines"]
    browser.post(f"/api/orders/suggestions/{line_a['id']}/decide", json={"decision": "approve"})

    to_order = browser.get("/api/today").json()["to_order"]
    assert to_order == {"lines": 1, "total_cost": line_b["line_cost"]}


def test_late_deliveries_only_when_sent_longer_ago_than_the_supplier_takes(browser):
    set_up_shop(browser)
    _, on_time_line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6, delivery_days=10)
    browser.post(f"/api/orders/suggestions/{on_time_line['id']}/decide", json={"decision": "approve"})
    [on_time_po] = browser.get("/api/orders/purchase-orders").json()
    browser.post(f"/api/orders/purchase-orders/{on_time_po['id']}/send")

    _, late_line = one_suggestion(browser, sku="OIL-2", per_week=5, on_hand=1, delivery_days=5)
    browser.post(f"/api/orders/suggestions/{late_line['id']}/decide", json={"decision": "approve"})
    pos = browser.get("/api/orders/purchase-orders").json()
    late_po = next(po for po in pos if po["id"] != on_time_po["id"])
    browser.post(f"/api/orders/purchase-orders/{late_po['id']}/send")

    with SessionLocal() as db:
        # On-time order sent 3 days ago (its supplier takes 10): not late.
        db.execute(update(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(on_time_po["id"])).values(
            sent_at=datetime.now(UTC) - timedelta(days=3)
        ))
        # Late order sent 9 days ago (its supplier takes 5): 4 days late.
        db.execute(update(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(late_po["id"])).values(
            sent_at=datetime.now(UTC) - timedelta(days=9)
        ))
        db.commit()

    late = browser.get("/api/today").json()["late_deliveries"]
    assert len(late) == 1
    assert late[0]["order_number"] == late_po["order_number"]
    assert late[0]["days_late"] == 4


def test_a_fully_received_order_is_never_late(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6, delivery_days=5)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()
    browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    with SessionLocal() as db:
        db.execute(update(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(po["id"])).values(
            sent_at=datetime.now(UTC) - timedelta(days=30)
        ))
        db.commit()
    detail = browser.get(f"/api/orders/purchase-orders/{po['id']}").json()
    [po_line] = detail["lines"]
    browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {po_line["id"]: po_line["quantity"]}})

    assert browser.get("/api/today").json()["late_deliveries"] == []


def test_weekly_sales_against_the_average_of_the_four_weeks_before(browser):
    set_up_shop(browser)
    shop = shop_id()
    first_day = LAST_DAY - timedelta(days=12 * 7 - 1)
    # The 4 weeks right before this one: 6, 8, 10, 8 sold -> average 8.
    for week, quantity in zip((7, 8, 9, 10), (6, 8, 10, 8), strict=True):
        add_sale(shop, first_day + timedelta(days=7 * week), quantity)
    # This week: 10 of the top part, 4 of another. One sale lands on LAST_DAY itself, so it is
    # the shop's last sales day and the window lines up exactly with the dates above.
    add_sale(shop, LAST_DAY, 10, sku="TOP-PART")
    add_sale(shop, LAST_DAY - timedelta(days=1), 4, sku="OTHER-PART")

    weekly = browser.get("/api/today").json()["weekly_sales"]
    assert weekly["this_week"] == 14
    assert weekly["normal"] == 8
    assert len(weekly["weeks"]) == 12
    assert weekly["weeks"][-1]["quantity"] == 14
    assert [p["sku"] for p in weekly["top_parts"]] == ["TOP-PART", "OTHER-PART"]
    assert [p["quantity"] for p in weekly["top_parts"]] == [10, 4]


def test_weekly_sales_is_none_without_any_sales_yet(browser):
    set_up_shop(browser)
    assert browser.get("/api/today").json()["weekly_sales"] is None


def test_today_only_shows_the_callers_own_shop(browser):
    set_up_shop(browser)
    other = create_other_shop()
    add_alert(other.organization_id, "negative_stock", 500)
    add_sale(other.organization_id, LAST_DAY, 99)

    data = browser.get("/api/today").json()
    assert data["needs_action_total"] == 0 and data["weekly_sales"] is None


def test_everyone_can_see_today_including_staff(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    assert staff.get("/api/today").status_code == 200


def test_staff_sees_no_money_anywhere_in_the_raw_json(browser):
    """Checked on the actual JSON, not just what the browser chooses to display."""
    set_up_shop(browser)
    shop = shop_id()
    add_alert(shop, "negative_stock", 14000)
    add_part(shop, sku="OIL-1", per_week=9, on_hand=6)
    browser.post("/api/orders/suggestions", json={})
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    owner_data = browser.get("/api/today").json()
    assert owner_data["needs_action"][0]["sentence"] == "Something unusual. About 140 MAD of stock to recount."
    assert owner_data["needs_action"][0]["money_at_stake"] == 14000

    staff_data = staff.get("/api/today").json()
    [staff_alert] = staff_data["needs_action"]
    assert "money_at_stake" not in staff_alert
    assert staff_alert["sentence"] == "Something unusual."
    assert "MAD" not in staff_alert["sentence"]
    assert staff_data["to_order"] == {"lines": 1}
    assert "total_cost" not in staff_data["to_order"]
    assert browser.get("/api/today").json()["to_order"]["total_cost"] > 0
