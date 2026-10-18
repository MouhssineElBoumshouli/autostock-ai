from sqlalchemy import select

from app.db import SessionLocal
from app.models import Branch, Part, SaleLine, StockLevel
from tests.helpers import add_member, audit_rows, create_other_shop, member_with_own_password, set_up_shop
from tests.import_helpers import send


def branch_map(browser) -> dict[str, str]:
    return {b["name"]: b["id"] for b in browser.get("/api/branches").json()}


def add_part(browser, sku: str, branch: str, quantity: int) -> None:
    content = f"SKU;Name;Quantity;Branch\n{sku};Widget;{quantity};{branch}\n".encode()
    response = send(browser, "save", "parts", "stock.csv", {0: "sku", 1: "name", 2: "quantity", 3: "branch"}, content=content)
    assert response.status_code == 200, response.text


def add_sale(browser, sku: str, branch: str) -> None:
    content = f"Date;SKU;Quantity;Branch\n01/10/2026;{sku};2;{branch}\n".encode()
    response = send(browser, "save", "sales", "sale.csv", {0: "date", 1: "sku", 2: "quantity", 3: "branch"}, content=content)
    assert response.status_code == 200, response.text


def test_owner_sees_branches_and_whether_each_is_used(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Casablanca", 5)

    branches = {b["name"]: b for b in browser.get("/api/branches").json()}

    assert branches["Atlas Parts"]["in_use"] is False
    assert branches["Casablanca"]["in_use"] is True


def test_owner_renames_a_branch(browser):
    set_up_shop(browser)
    atlas_id = branch_map(browser)["Atlas Parts"]

    response = browser.patch(f"/api/branches/{atlas_id}", json={"name": "Main Warehouse"})

    assert response.json()["name"] == "Main Warehouse"
    row = audit_rows("branch.renamed")[-1]
    assert row.before == {"name": "Atlas Parts"}
    assert row.after == {"name": "Main Warehouse"}


def test_renaming_to_an_existing_name_is_rejected(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Casablanca", 1)
    ids = branch_map(browser)

    response = browser.patch(f"/api/branches/{ids['Casablanca']}", json={"name": "atlas parts"})

    assert response.status_code == 409
    assert response.json()["detail"] == "A branch with this name already exists."


def test_merge_combines_stock_sums_quantities_and_moves_sales(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Casablanca", 5)
    add_part(browser, "AA-1", "Rabat", 3)
    add_sale(browser, "AA-1", "Rabat")
    ids = branch_map(browser)

    response = browser.post(f"/api/branches/{ids['Rabat']}/merge", json={"into": ids["Casablanca"]})

    assert response.status_code == 204
    assert sorted(b["name"] for b in browser.get("/api/branches").json()) == ["Atlas Parts", "Casablanca"]
    with SessionLocal() as db:
        part = db.scalar(select(Part).where(Part.sku == "AA-1"))
        level = db.scalar(select(StockLevel).where(StockLevel.part_id == part.id))
        assert level.quantity == 8
        assert str(level.branch_id) == ids["Casablanca"]
        sale = db.scalar(select(SaleLine).where(SaleLine.part_id == part.id))
        assert str(sale.branch_id) == ids["Casablanca"]
        assert db.scalar(select(Branch).where(Branch.id == ids["Rabat"])) is None
    row = audit_rows("branch.merged")[-1]
    assert row.after == {"from": "Rabat", "into": "Casablanca"}


def test_cannot_merge_a_branch_into_itself(browser):
    set_up_shop(browser)
    atlas_id = branch_map(browser)["Atlas Parts"]

    response = browser.post(f"/api/branches/{atlas_id}/merge", json={"into": atlas_id})

    assert response.status_code == 422


def test_owner_removes_an_unused_branch(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Casablanca", 1)
    ids = branch_map(browser)

    response = browser.delete(f"/api/branches/{ids['Atlas Parts']}")

    assert response.status_code == 204
    assert [b["name"] for b in browser.get("/api/branches").json()] == ["Casablanca"]
    row = audit_rows("branch.removed")[-1]
    assert row.before == {"name": "Atlas Parts"}


def test_cannot_remove_a_branch_with_stock_or_sales(browser):
    set_up_shop(browser)
    add_part(browser, "AA-1", "Casablanca", 1)
    ids = branch_map(browser)

    response = browser.delete(f"/api/branches/{ids['Casablanca']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "This branch has stock or sales history. Merge it into another branch first."


def test_cannot_remove_the_last_branch(browser):
    set_up_shop(browser)
    atlas_id = branch_map(browser)["Atlas Parts"]

    response = browser.delete(f"/api/branches/{atlas_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "The shop needs at least one branch."


def test_staff_and_manager_cannot_manage_branches(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    add_member(browser, "staff@shop.ma", "staff")
    atlas_id = branch_map(browser)["Atlas Parts"]

    for email in ["manager@shop.ma", "staff@shop.ma"]:
        member = member_with_own_password(email)
        assert member.get("/api/branches").status_code == 403
        assert member.patch(f"/api/branches/{atlas_id}", json={"name": "X"}).status_code == 403


def test_owner_cannot_manage_another_shops_branches(browser):
    set_up_shop(browser)
    other_owner = create_other_shop()
    with SessionLocal() as db:
        other_branch = db.scalar(select(Branch).where(Branch.organization_id == other_owner.organization_id))

    response = browser.patch(f"/api/branches/{other_branch.id}", json={"name": "Stolen"})

    assert response.status_code == 404
