"""Approving suggestions into draft purchase orders, sending them, and receiving stock."""

from datetime import timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Branch, Forecast, Part, PurchaseOrder, SaleLine, StockLevel, Supplier
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, run_lines, set_up_shop
from tests.test_orders import LAST_DAY, add_part, shop_id


def one_suggestion(browser, **kwargs) -> tuple[str, dict]:
    part = add_part(shop_id(), **kwargs)
    run = browser.post("/api/orders/suggestions", json={}).json()
    [line] = [line for line in run_lines(browser, run) if line["part_id"] == str(part)]
    return part, line


def test_approving_a_line_creates_a_draft_purchase_order(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)

    response = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["status"] == "approved"
    assert approved["approved_quantity"] == line["quantity"]

    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["status"] == "draft" and po["order_number"] == "PO-0001"
    assert po["line_count"] == 1
    assert po["total_cost"] == line["line_cost"]
    [row] = audit_rows("purchase_order.created")
    assert row.after["order_number"] == "PO-0001"


def test_manager_can_change_the_quantity_when_approving(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)

    custom = line["quantity"] + 10
    response = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve", "quantity": custom})
    assert response.json()["approved_quantity"] == custom

    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["total_cost"] == custom * line["unit_cost"]


def test_rejecting_removes_an_approved_line_and_the_empty_order(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})

    response = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "reject"})
    assert response.json()["status"] == "rejected"
    assert browser.get("/api/orders/purchase-orders").json() == []


def test_approve_all_for_one_supplier(browser):
    set_up_shop(browser)
    shop = shop_id()
    with SessionLocal() as db:
        supplier = Supplier(organization_id=shop, name="Shared Supplier", delivery_days=14)
        db.add(supplier)
        db.commit()
        supplier_id = supplier.id
    part_a = add_part(shop, sku="OIL-1", per_week=9, on_hand=6)
    part_b = add_part(shop, sku="OIL-2", per_week=5, on_hand=1)
    with SessionLocal() as db:
        db.execute(update(Part).where(Part.id.in_([part_a, part_b])).values(supplier_id=supplier_id))
        db.commit()

    run = browser.post("/api/orders/suggestions", json={}).json()
    response = browser.post(f"/api/orders/runs/{run['id']}/suppliers/{supplier_id}/approve-all")
    assert response.status_code == 200, response.text
    assert response.json() == {"approved": 2}
    assert all(line["status"] == "approved" for line in run_lines(browser, run))
    [group] = browser.get("/api/orders/suggestions/latest").json()["groups"]
    assert group["pending_count"] == 0
    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["line_count"] == 2


def test_approving_a_cut_by_budget_line_overrides_the_budget(browser):
    set_up_shop(browser)
    shop = shop_id()
    add_part(shop, sku="LOW-MARGIN", per_week=9, on_hand=0, unit_cost=9500, sale_price=10000)
    add_part(shop, sku="HIGH-MARGIN", per_week=9, on_hand=0, unit_cost=5000, sale_price=10000)
    everything = browser.post("/api/orders/suggestions", json={}).json()
    one_line = max(line["line_cost"] for line in run_lines(browser, everything))
    run = browser.post("/api/orders/suggestions", json={"budget": one_line}).json()
    cut = next(line for line in run_lines(browser, run) if line["status"] == "cut_by_budget")

    response = browser.post(f"/api/orders/suggestions/{cut['id']}/decide", json={"decision": "approve"})
    assert response.json()["status"] == "approved"
    [po] = browser.get("/api/orders/purchase-orders").json()
    assert po["line_count"] == 1


def test_sending_locks_the_line_and_counts_as_already_ordered_next_run(browser):
    set_up_shop(browser)
    part, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()

    response = browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    assert response.status_code == 200
    sent = response.json()
    assert sent["status"] == "sent" and sent["sent_at"] is not None

    again = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "reject"})
    assert again.status_code == 409

    # Demand doubles before the next review, so on_order covers only part of the new need
    # (otherwise the part needs nothing more and wouldn't show up at all).
    with SessionLocal() as db:
        db.execute(update(Forecast).where(Forecast.part_id == part).values(quantity=Forecast.quantity * 2, high=Forecast.high * 2))
        db.commit()
    next_run = browser.post("/api/orders/suggestions", json={}).json()
    [next_line] = [row for row in run_lines(browser, next_run) if row["part_id"] == str(part)]
    assert next_line["on_order"] == line["quantity"]
    assert next_line["quantity"] > 0


def test_receiving_in_full_adds_stock_and_marks_received(browser):
    set_up_shop(browser)
    part, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()
    browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    detail = browser.get(f"/api/orders/purchase-orders/{po['id']}").json()
    [po_line] = detail["lines"]

    response = browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {po_line["id"]: po_line["quantity"]}})
    assert response.status_code == 200, response.text
    received = response.json()
    assert received["status"] == "received" and received["received_at"] is not None

    with SessionLocal() as db:
        level = db.scalar(select(StockLevel).where(StockLevel.part_id == part))
        assert level.quantity == 6 + po_line["quantity"]
    assert audit_rows("purchase_order.received")


def test_receiving_partially_keeps_the_order_sent(browser):
    set_up_shop(browser)
    part, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()
    browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    detail = browser.get(f"/api/orders/purchase-orders/{po['id']}").json()
    [po_line] = detail["lines"]
    assert po_line["quantity"] > 1

    partial = browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {po_line["id"]: 1}}).json()
    assert partial["status"] == "sent"
    assert partial["lines"][0]["received_quantity"] == 1

    rest = po_line["quantity"] - 1
    final = browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {po_line["id"]: rest}}).json()
    assert final["status"] == "received"


def test_receiving_more_than_ordered_is_refused(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()
    browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    detail = browser.get(f"/api/orders/purchase-orders/{po['id']}").json()
    [po_line] = detail["lines"]

    response = browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {po_line["id"]: po_line["quantity"] + 1}})
    assert response.status_code == 422


def test_cannot_send_twice_or_receive_a_draft(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()

    assert browser.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {}}).status_code == 409
    browser.post(f"/api/orders/purchase-orders/{po['id']}/send")
    assert browser.post(f"/api/orders/purchase-orders/{po['id']}/send").status_code == 409


def test_approving_a_part_with_no_supplier_is_refused(browser):
    set_up_shop(browser)
    shop = shop_id()
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == shop))
        part = Part(organization_id=shop, sku="NO-SUPPLIER", name="No supplier part", unit_cost=1000, sale_price=2000)
        db.add(part)
        db.flush()
        db.add(Forecast(organization_id=shop, part_id=part.id, branch_id=branch.id, horizon_days=30,
                        history_last_day=LAST_DAY, demand_type="smooth", method="four_week_average", quantity=30,
                        low=20, high=40, backtest_windows=12, reason="test"))
        db.add(StockLevel(organization_id=shop, part_id=part.id, branch_id=branch.id, quantity=0))
        db.add(SaleLine(organization_id=shop, sold_on=LAST_DAY - timedelta(days=3), part_id=part.id,
                        branch_id=branch.id, quantity=2))
        db.commit()

    run = browser.post("/api/orders/suggestions", json={}).json()
    [line] = run_lines(browser, run)
    response = browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    assert response.status_code == 422


def test_order_settings_default_and_only_owner_can_change_them(browser):
    set_up_shop(browser)
    assert browser.get("/api/orders/settings").json() == {"service_target": 0.9}

    changed = browser.patch("/api/orders/settings", json={"service_target": 0.95})
    assert changed.status_code == 200 and changed.json()["service_target"] == 0.95

    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")
    assert manager.get("/api/orders/settings").status_code == 403
    assert manager.patch("/api/orders/settings", json={"service_target": 0.8}).status_code == 403


def test_a_more_careful_target_orders_a_bigger_safety_cushion(browser):
    set_up_shop(browser)
    add_part(shop_id(), sku="OIL-1", per_week=9, on_hand=6)

    browser.patch("/api/orders/settings", json={"service_target": 0.8})
    cautious_off = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())[0]["cushion"]
    browser.patch("/api/orders/settings", json={"service_target": 0.95})
    cautious_on = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())[0]["cushion"]
    assert cautious_on > cautious_off


def test_staff_can_view_purchase_orders_but_not_change_them(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    [po] = browser.get("/api/orders/purchase-orders").json()

    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    assert staff.get("/api/orders/purchase-orders").status_code == 200
    assert staff.get(f"/api/orders/purchase-orders/{po['id']}").status_code == 200
    assert staff.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "reject"}).status_code == 403
    assert staff.post(f"/api/orders/purchase-orders/{po['id']}/send").status_code == 403
    assert staff.post(f"/api/orders/purchase-orders/{po['id']}/receive", json={"lines": {}}).status_code == 403


def test_each_shop_only_sees_its_own_purchase_orders(browser):
    set_up_shop(browser)
    _, line = one_suggestion(browser, sku="OIL-1", per_week=9, on_hand=6)
    browser.post(f"/api/orders/suggestions/{line['id']}/decide", json={"decision": "approve"})
    create_other_shop()

    assert len(browser.get("/api/orders/purchase-orders").json()) == 1
    with SessionLocal() as db:
        organizations = {row.organization_id for row in db.scalars(select(PurchaseOrder))}
        assert organizations == {shop_id()}
