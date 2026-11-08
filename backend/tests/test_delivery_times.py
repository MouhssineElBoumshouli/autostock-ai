"""Suppliers' delivery times without typing: from the shop's parts file, then from its real
deliveries; 7 days estimated until then. The owner may still choose one."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal, utc_now
from app.imports.matching import suggest_field
from app.imports.values import ValueProblem, parse_delivery_days
from app.models import Branch, Part, PurchaseOrder, PurchaseOrderLine, StockLevel, Supplier
from tests.helpers import audit_rows, run_lines, set_up_shop
from tests.import_helpers import send
from tests.test_orders import add_part, shop_id

PARTS = {0: "sku", 1: "name", 2: "supplier", 3: "delivery_days", 4: "quantity"}


def supplier(name: str) -> Supplier:
    with SessionLocal() as db:
        return db.scalar(select(Supplier).where(Supplier.name == name))


def import_csv(browser, text: str, mapping: dict = PARTS) -> dict:
    response = send(browser, "save", "parts", "pieces.csv", mapping, content=text.encode())
    assert response.status_code == 200, response.text
    return response.json()


# --- the column is found by itself ---

@pytest.mark.parametrize("header", [
    "Délai de livraison", "Délai (jours)", "Délai de livraison (jours)", "Lead time", "Lead time (days)",
    "LEAD_TIME", "Delivery time", "Livraison (j)", "delai", "مدة التوصيل", "مدة التسليم (أيام)",
])
def test_a_delivery_time_column_is_matched_by_itself(header):
    assert suggest_field(header, "parts") == "delivery_days"


@pytest.mark.parametrize("header", ["Délai de paiement", "Date de livraison", "Adresse de livraison", "Dernière livraison",
                                    "Payment lead time", "Frais de livraison"])
def test_columns_that_only_look_like_it_are_not(header):
    assert suggest_field(header, "parts") != "delivery_days"


@pytest.mark.parametrize("cell, days", [
    (5, 5), (2.5, 3), ("5", 5), ("5 jours", 5), ("5j", 5), ("3-5 jours", 5), ("2 semaines", 14), ("une semaine", 7),
    ("1 mois", 30), ("48h", 2), ("72 heures", 3), ("١٠ أيام", 10), ("أسبوعين", 14), ("15 jours hors week-end", 15),
    ("10 days", 10), (0, 0), ("", None), (None, None),
])
def test_delivery_time_cells_are_read_as_days(cell, days):
    assert parse_delivery_days(cell) == days


@pytest.mark.parametrize("cell", ["sur commande", "15/03/2026", "45678", -3])
def test_cells_that_are_not_a_delivery_time_are_refused(cell):
    with pytest.raises(ValueProblem):
        parse_delivery_days(cell)


# --- from the shop's file ---

def test_the_parts_file_sets_each_suppliers_most_common_delivery_time(browser):
    set_up_shop(browser)

    summary = import_csv(browser, "SKU;Name;Supplier;Délai;Qty\n"
                                  "BP-1;Brake pads;Atlas;3 jours;5\n"
                                  "BP-2;Brake discs;Atlas;3;2\n"
                                  "BP-3;Brake fluid;Atlas;10;1\n"
                                  "OF-1;Oil filter;Sud Import;3 semaines;4\n"
                                  "OF-2;Air filter;Sud Import;sur commande;4\n")

    assert summary["counts"]["delivery_times"] == 2
    assert summary["counts"]["unread_delivery_times"] == 1
    assert summary["counts"]["problem_rows"] == 0  # a delivery time that can't be read never leaves a part out
    atlas, sud = supplier("Atlas"), supplier("Sud Import")
    assert (atlas.delivery_days, atlas.delivery_source) == (3, "file")
    assert (sud.delivery_days, sud.delivery_source) == (21, "file")
    rows = audit_rows("supplier.delivery_time_changed")
    assert {row.after["name"]: row.after["delivery_days"] for row in rows} == {"Atlas": 3, "Sud Import": 21}
    with SessionLocal() as db:
        assert db.scalar(select(Part).where(Part.sku == "OF-2")) is not None


def test_a_row_without_supplier_sets_its_parts_supplier(browser):
    set_up_shop(browser)
    import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;;5\n")

    import_csv(browser, "SKU;Name;Lead time\nBP-1;Brake pads;4\n", {0: "sku", 1: "name", 2: "delivery_days"})

    assert supplier("Atlas").delivery_days == 4


def test_the_file_never_replaces_the_owners_choice(browser):
    set_up_shop(browser)
    import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;;5\n")
    atlas_id = supplier("Atlas").id
    browser.patch(f"/api/suppliers/{atlas_id}/details", json={"delivery_days": 9})

    summary = import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;3;5\n")

    assert summary["counts"]["delivery_times"] == 0
    atlas = supplier("Atlas")
    assert (atlas.delivery_days, atlas.delivery_source) == (9, "owner")


def test_a_new_file_replaces_an_earlier_files_delivery_time(browser):
    set_up_shop(browser)
    import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;3;5\n")

    import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;5;5\n")

    assert supplier("Atlas").delivery_days == 5


def test_an_unchanged_file_saves_nothing_new(browser):
    set_up_shop(browser)
    text = "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;3;5\n"
    import_csv(browser, text)

    again = send(browser, "check", "parts", "pieces.csv", PARTS, content=text.encode()).json()

    assert again["counts"]["delivery_times"] == again["counts"]["delivery_only"] == 0
    assert again["counts"]["updated_parts"] == 0


def test_a_new_part_in_the_file_means_a_normal_import(browser):
    set_up_shop(browser)
    import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;;5\n")

    summary = import_csv(browser, "SKU;Name;Supplier;Délai;Qty\nBP-1;Brake pads;Atlas;3;8\nBP-2;Discs;Atlas;3;1\n")

    assert summary["counts"]["delivery_only"] == 0
    assert summary["counts"]["new_parts"] == 1 and summary["counts"]["updated_parts"] == 1
    assert supplier("Atlas").delivery_days == 3
    with SessionLocal() as db:
        assert db.scalar(select(StockLevel.quantity).join(Part).where(Part.sku == "BP-1")) == 8


# --- from real deliveries ---

def receive_after(browser, supplier_id, days: int) -> dict:
    """A sent order to this supplier, sent `days` ago, received now in full."""
    with SessionLocal() as db:
        found = db.get_one(Supplier, supplier_id)
        branch = db.scalar(select(Branch).where(Branch.organization_id == found.organization_id))
        part = db.scalar(select(Part).where(Part.supplier_id == supplier_id))
        count = len(db.scalars(select(PurchaseOrder.id).where(PurchaseOrder.organization_id == found.organization_id)).all())
        po = PurchaseOrder(organization_id=found.organization_id, supplier_id=supplier_id, order_number=f"PO-{count + 1:04d}",
                           status="sent", sent_at=utc_now() - timedelta(days=days))
        db.add(po)
        db.flush()
        line = PurchaseOrderLine(organization_id=found.organization_id, purchase_order_id=po.id, part_id=part.id,
                                 branch_id=branch.id, quantity=2, unit_cost=7000)
        db.add(line)
        db.commit()
        po_id, line_id = po.id, line.id
    response = browser.post(f"/api/orders/purchase-orders/{po_id}/receive", json={"lines": {str(line_id): 2}})
    assert response.status_code == 200, response.text
    return response.json()


def supplier_of(part_id) -> Supplier:
    with SessionLocal() as db:
        return db.get_one(Supplier, db.get_one(Part, part_id).supplier_id)


def delivery_shown(browser, supplier_id) -> dict:
    [found] = [s for s in browser.get("/api/suppliers").json() if s["id"] == str(supplier_id)]
    return found["delivery"]


def test_a_received_order_records_how_many_days_it_took(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id

    receive_after(browser, supplier_id, days=4)

    with SessionLocal() as db:
        assert db.scalar(select(PurchaseOrder.days_taken)) == 4
    assert audit_rows("purchase_order.received")[-1].after["days_taken"] == 4


def test_the_first_delivery_replaces_the_estimate(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    assert delivery_shown(browser, supplier_id) == {"days": 7, "source": "estimated", "learned_from": 0}

    receive_after(browser, supplier_id, days=4)

    assert delivery_shown(browser, supplier_id) == {"days": 4, "source": "learned", "learned_from": 1}
    assert audit_rows("supplier.delivery_time_changed")[-1].after["source"] == "learned"


def test_same_day_counts_as_one_day(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)

    receive_after(browser, supplier_of(part).id, days=0)

    assert supplier_of(part).delivery_days == 1


def test_it_follows_the_typical_value_of_the_last_five_deliveries(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id

    for days in (30, 30, 30, 3, 4, 5, 20, 4):  # the three oldest are too old to count
        receive_after(browser, supplier_id, days)

    # The last five, sorted: 3, 4, 4, 5, 20 -> 4. All eight would give 20.
    assert delivery_shown(browser, supplier_id) == {"days": 4, "source": "learned", "learned_from": 5}


def test_two_deliveries_take_the_longer_middle_value(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id

    receive_after(browser, supplier_id, 3)
    receive_after(browser, supplier_id, 10)

    assert supplier_of(part).delivery_days == 10


def test_a_files_delivery_time_holds_until_three_real_deliveries(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    with SessionLocal() as db:
        found = db.get_one(Supplier, supplier_id)
        found.delivery_days, found.delivery_source = 3, "file"
        db.commit()

    receive_after(browser, supplier_id, 8)
    receive_after(browser, supplier_id, 9)
    assert delivery_shown(browser, supplier_id) == {"days": 3, "source": "file", "learned_from": 0}

    receive_after(browser, supplier_id, 8)
    assert delivery_shown(browser, supplier_id) == {"days": 8, "source": "learned", "learned_from": 3}


def test_the_owners_choice_stays_and_emptying_it_goes_back_to_automatic(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": 10})

    receive_after(browser, supplier_id, 4)
    assert delivery_shown(browser, supplier_id) == {"days": 10, "source": "owner", "learned_from": 0}

    response = browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": None})

    assert response.json()["delivery"] == {"days": 4, "source": "learned", "learned_from": 1}
    assert audit_rows("supplier.delivery_time_changed")[-2].after["delivery_days"] is None


def test_saving_contact_details_does_not_pin_a_learned_delivery_time(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    receive_after(browser, supplier_id, 4)

    browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": 4, "phone": "+212 600"})

    assert delivery_shown(browser, supplier_id)["source"] == "learned"


def test_order_lines_say_where_the_delivery_time_came_from(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    receive_after(browser, supplier_of(part).id, 4)
    receive_after(browser, supplier_of(part).id, 6)

    [line] = run_lines(browser, browser.post("/api/orders/suggestions", json={}).json())

    assert (line["delivery_days"], line["delivery_source"], line["delivery_learned_from"]) == (6, "learned", 2)
    assert "supplier takes 6 days (learned from 2 deliveries)" in line["reason"]


def test_the_activity_page_gets_what_it_needs_to_say_what_changed(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": 6})

    items = browser.get("/api/activity").json()["items"]

    [changed] = [item for item in items if item["action"] == "supplier.delivery_time_changed"]
    assert changed["after"] == {"name": "Supplier OIL-1", "delivery_days": 6, "source": "owner", "learned_from": 0}


def test_settings_says_when_real_deliveries_disagree_with_a_typed_delivery_time(browser):
    set_up_shop(browser)
    part = add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)
    supplier_id = supplier_of(part).id
    browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": 5})

    def shown() -> dict:
        [found] = [s for s in browser.get("/api/suppliers").json() if s["id"] == str(supplier_id)]
        return found

    receive_after(browser, supplier_id, 12)
    receive_after(browser, supplier_id, 11)
    assert shown()["deliveries_say"] is None  # two deliveries are not enough to say so

    receive_after(browser, supplier_id, 13)
    found = shown()
    assert found["deliveries_say"] == {"days": 12, "count": 3}
    assert found["delivery"] == {"days": 5, "source": "owner", "learned_from": 0}  # it stays what was typed

    # The one click: back to automatic, which follows those deliveries.
    after = browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": None}).json()
    assert after["delivery"] == {"days": 12, "source": "learned", "learned_from": 3}
    assert after["deliveries_say"] is None


def test_no_hint_when_deliveries_agree_or_nothing_was_typed(browser):
    set_up_shop(browser)
    typed = supplier_of(add_part(shop_id(), "OIL-1", per_week=9, on_hand=6, delivery_days=None)).id
    automatic = supplier_of(add_part(shop_id(), "OIL-2", per_week=9, on_hand=6, delivery_days=None)).id
    browser.patch(f"/api/suppliers/{typed}/details", json={"delivery_days": 4})
    for days in (4, 4, 5):
        receive_after(browser, typed, days)
        receive_after(browser, automatic, days + 6)

    hints = {s["id"]: s["deliveries_say"] for s in browser.get("/api/suppliers").json()}

    assert hints == {str(typed): None, str(automatic): None}
