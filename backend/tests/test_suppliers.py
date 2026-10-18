from sqlalchemy import select

from app.db import SessionLocal
from app.models import Part, Supplier
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, set_up_shop
from tests.import_helpers import send


def supplier_map(browser) -> dict[str, str]:
    return {s["name"]: s["id"] for s in browser.get("/api/suppliers").json()}


def add_part(browser, sku: str, supplier: str) -> None:
    content = f"SKU;Name;Supplier\n{sku};Widget;{supplier}\n".encode()
    response = send(browser, "save", "parts", "stock.csv", {0: "sku", 1: "name", 2: "supplier"}, content=content)
    assert response.status_code == 200, response.text


def test_owner_sees_suppliers_and_whether_each_is_used(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")

    suppliers = {s["name"]: s for s in browser.get("/api/suppliers").json()}

    assert suppliers["Auto Hall"]["in_use"] is True


def test_owner_renames_a_supplier(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    supplier_id = supplier_map(browser)["Auto Hall"]

    response = browser.patch(f"/api/suppliers/{supplier_id}", json={"name": "Auto Hall Pieces"})

    assert response.json()["name"] == "Auto Hall Pieces"
    row = audit_rows("supplier.renamed")[-1]
    assert row.before == {"name": "Auto Hall"}
    assert row.after == {"name": "Auto Hall Pieces"}


def test_renaming_to_an_existing_name_is_rejected(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    add_part(browser, "AA-2", "Brembo Maroc")
    ids = supplier_map(browser)

    response = browser.patch(f"/api/suppliers/{ids['Brembo Maroc']}", json={"name": "auto hall"})

    assert response.status_code == 409
    assert response.json()["detail"] == "A supplier with this name already exists."


def test_merge_moves_parts_and_removes_source(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    add_part(browser, "AA-2", "Auto Hall Pieces")  # a duplicate created by a typo
    ids = supplier_map(browser)

    response = browser.post(f"/api/suppliers/{ids['Auto Hall Pieces']}/merge", json={"into": ids["Auto Hall"]})

    assert response.status_code == 204
    assert [s["name"] for s in browser.get("/api/suppliers").json()] == ["Auto Hall"]
    with SessionLocal() as db:
        for sku in ("AA-1", "AA-2"):
            part = db.scalar(select(Part).where(Part.sku == sku))
            assert str(part.supplier_id) == ids["Auto Hall"]
        assert db.scalar(select(Supplier).where(Supplier.id == ids["Auto Hall Pieces"])) is None
    row = audit_rows("supplier.merged")[-1]
    assert row.after == {"from": "Auto Hall Pieces", "into": "Auto Hall"}


def test_cannot_merge_a_supplier_into_itself(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    supplier_id = supplier_map(browser)["Auto Hall"]

    response = browser.post(f"/api/suppliers/{supplier_id}/merge", json={"into": supplier_id})

    assert response.status_code == 422


def test_owner_removes_an_unused_supplier(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Brembo Maroc")
    add_part(browser, "AA-1", "Auto Hall")  # the part's supplier was corrected, leaving Brembo Maroc unused
    ids = supplier_map(browser)

    response = browser.delete(f"/api/suppliers/{ids['Brembo Maroc']}")

    assert response.status_code == 204
    assert [s["name"] for s in browser.get("/api/suppliers").json()] == ["Auto Hall"]
    row = audit_rows("supplier.removed")[-1]
    assert row.before == {"name": "Brembo Maroc"}


def test_cannot_remove_a_supplier_used_by_parts(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    supplier_id = supplier_map(browser)["Auto Hall"]

    response = browser.delete(f"/api/suppliers/{supplier_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "This supplier is used by some parts. Merge it into another supplier first."


def test_staff_and_manager_cannot_manage_suppliers(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Auto Hall")
    add_member(browser, "manager@shop.ma", "manager")
    add_member(browser, "staff@shop.ma", "staff")
    supplier_id = supplier_map(browser)["Auto Hall"]

    for email in ["manager@shop.ma", "staff@shop.ma"]:
        member = member_with_own_password(email)
        assert member.get("/api/suppliers").status_code == 403
        assert member.patch(f"/api/suppliers/{supplier_id}", json={"name": "X"}).status_code == 403


def test_owner_cannot_manage_another_shops_suppliers(browser):
    set_up_shop(browser)
    other_owner = create_other_shop()
    with SessionLocal() as db:
        other_supplier = Supplier(organization_id=other_owner.organization_id, name="Other Shop's Supplier")
        db.add(other_supplier)
        db.commit()
        other_supplier_id = other_supplier.id

    response = browser.patch(f"/api/suppliers/{other_supplier_id}", json={"name": "Stolen"})

    assert response.status_code == 404
