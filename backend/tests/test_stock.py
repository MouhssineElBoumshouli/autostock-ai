from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Part
from tests.helpers import (
    OWNER_PASSWORD,
    add_member,
    audit_rows,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    set_up_shop,
)
from tests.import_helpers import import_parts, import_sales, send


def parts(browser, **params) -> dict:
    response = browser.get("/api/stock/parts", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def skus(page: dict) -> list[str]:
    return [item["sku"] for item in page["items"]]


def part_id(sku: str) -> str:
    with SessionLocal() as db:
        return str(db.scalar(select(Part.id).where(Part.sku == sku)))


def shop_with_parts(browser):
    set_up_shop(browser)
    import_parts(browser)


def test_stat_cards_count_real_parts(browser):
    shop_with_parts(browser)

    assert browser.get("/api/stock/summary").json() == {"all": 22, "healthy": 15, "low": 4, "out": 3}


def test_empty_shop_has_zero_everywhere(browser):
    set_up_shop(browser)

    assert browser.get("/api/stock/summary").json() == {"all": 0, "healthy": 0, "low": 0, "out": 0}
    assert parts(browser)["total"] == 0


def test_list_shows_quantity_status_and_supplier(browser):
    shop_with_parts(browser)

    item = next(i for i in parts(browser, search="BP-001")["items"])

    assert item["name"] == "Plaquettes de frein avant"
    assert (item["quantity"], item["min_stock"], item["status"]) == (6, 10, "low")
    assert item["supplier"] == "Auto Hall Pièces"


def test_search_by_name_sku_or_oem_reference(browser):
    shop_with_parts(browser)

    assert sorted(skus(parts(browser, search="frein"))) == ["BP-001", "BP-002", "DS-110"]
    assert skus(parts(browser, search="w 712")) == ["FL-200"]
    assert sorted(skus(parts(browser, search="sp-10"))) == ["SP-104", "SP-105"]
    assert parts(browser, search="100%")["total"] == 0  # special characters are searched as text


def test_filters(browser):
    shop_with_parts(browser)
    filters = browser.get("/api/stock/filters").json()
    rabat = next(b["id"] for b in filters["branches"] if b["name"] == "Rabat")
    varta = next(s["id"] for s in filters["suppliers"] if s["name"] == "Varta Maroc")

    assert "Freinage" in filters["categories"]
    assert sorted(skus(parts(browser, status="out"))) == ["DS-110", "RL-701", "SP-104"]
    assert sorted(skus(parts(browser, status="low"))) == ["BP-001", "BT-913", "FL-205", "PE-600"]
    assert parts(browser, category="Freinage")["total"] == 3
    assert sorted(skus(parts(browser, supplier=varta))) == ["BT-912", "BT-913"]
    in_rabat = {i["sku"]: i["quantity"] for i in parts(browser, branch=rabat)["items"]}
    assert in_rabat["FL-205"] == 9
    assert in_rabat["BP-001"] == 0  # its stock is in Casablanca


def test_sort_by_any_column(browser):
    shop_with_parts(browser)

    assert skus(parts(browser, sort="quantity", direction="desc"))[0] == "FL-200"
    assert parts(browser, sort="status")["items"][0]["status"] == "out"
    assert skus(parts(browser, sort="sku"))[:2] == ["AM-300", "AM-301"]
    assert browser.get("/api/stock/parts", params={"sort": "nonsense"}).status_code == 422


def test_dead_stock_means_stock_but_no_sale_in_90_days(browser):
    shop_with_parts(browser)
    recent = (date.today() - timedelta(days=10)).strftime("%d/%m/%Y")
    old = (date.today() - timedelta(days=120)).strftime("%d/%m/%Y")
    sales = f"Date;SKU;Qty\n{recent};BP-002;1\n{old};FL-200;2\n".encode()
    send(browser, "save", "sales", "sales.csv", {0: "date", 1: "sku", 2: "quantity"}, content=sales)

    dead = skus(parts(browser, status="dead"))

    assert "BP-002" not in dead  # sold 10 days ago
    assert "FL-200" in dead  # last sale 120 days ago
    assert "DS-110" not in dead  # nothing in stock, so not dead stock
    assert len(dead) == 18


def test_50_per_page(browser):
    set_up_shop(browser)
    me = browser.get("/api/auth/me").json()
    with SessionLocal() as db:
        db.add_all(
            Part(organization_id=me["organization"]["id"], sku=f"P-{n:04d}", name=f"Part {n}", min_stock=0, is_active=True)
            for n in range(120)
        )
        db.commit()

    first, third = parts(browser, sort="sku"), parts(browser, sort="sku", page=3)

    assert first["total"] == 120
    assert len(first["items"]) == 50
    assert len(third["items"]) == 20
    assert third["items"][0]["sku"] == "P-0100"


def test_part_detail(browser):
    shop_with_parts(browser)
    import_sales(browser)

    detail = browser.get(f"/api/parts/{part_id('BP-001')}").json()

    assert detail["sale_price"] == 32000
    assert detail["status"] == "low"
    assert {row["branch"]: row["quantity"] for row in detail["stock"]} == {"Atlas Parts": 0, "Casablanca": 6, "Rabat": 0}
    assert detail["supplier"]["name"] == "Auto Hall Pièces"
    assert [(s["sold_on"], s["quantity"]) for s in detail["last_sales"]] == [("2026-10-14", 1), ("2026-10-03", 2)]


def test_last_sales_shows_10_newest(browser):
    shop_with_parts(browser)
    import_sales(browser, "sales_en_clean.xlsx")

    sales = browser.get(f"/api/parts/{part_id('BP-001')}").json()["last_sales"]

    assert len(sales) == 10
    assert sales[0]["sold_on"] == "2026-10-05"  # the file's last week


def test_manager_edits_a_part_and_it_is_audited(browser):
    shop_with_parts(browser)
    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")
    detail = manager.get(f"/api/parts/{part_id('BP-001')}").json()
    rabat = next(row["branch_id"] for row in detail["stock"] if row["branch"] == "Rabat")

    response = manager.patch(
        f"/api/parts/{detail['id']}",
        json={"min_stock": 4, "sale_price": 33000, "brand": None, "stock": [{"branch_id": rabat, "quantity": 5}]},
    )

    changed = response.json()
    assert (changed["min_stock"], changed["sale_price"], changed["brand"], changed["quantity"]) == (4, 33000, None, 11)
    assert changed["status"] == "healthy"
    row = audit_rows("part.updated")[-1]
    assert (row.before["min_stock"], row.after["min_stock"]) == (10, 4)
    assert (row.before["stock"]["Rabat"], row.after["stock"]["Rabat"]) == (0, 5)
    activity = browser.get("/api/activity?kind=stock").json()["items"]
    assert activity[0]["action"] == "part.updated"
    assert activity[0]["after"]["sku"] == "BP-001"


def test_saving_without_changes_writes_no_audit_row(browser):
    shop_with_parts(browser)

    browser.patch(f"/api/parts/{part_id('BP-001')}", json={"min_stock": 10})

    assert audit_rows("part.updated") == []


def test_staff_can_see_but_not_edit(browser):
    shop_with_parts(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    bp = part_id("BP-001")

    assert staff.get("/api/stock/summary").status_code == 200
    assert staff.get("/api/stock/parts").status_code == 200
    assert staff.get(f"/api/parts/{bp}").status_code == 200
    assert staff.patch(f"/api/parts/{bp}", json={"min_stock": 1}).status_code == 403


def test_one_shop_cannot_see_or_edit_another_shops_parts(browser):
    shop_with_parts(browser)
    create_other_shop()
    other = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    bp = part_id("BP-001")

    assert other.get("/api/stock/summary").json()["all"] == 0
    assert other.get("/api/stock/parts").json()["total"] == 0
    assert other.get(f"/api/parts/{bp}").status_code == 404
    assert other.patch(f"/api/parts/{bp}", json={"min_stock": 1}).status_code == 404
    filters = other.get("/api/stock/filters").json()
    assert (filters["categories"], filters["suppliers"]) == ([], [])
    assert [branch["name"] for branch in filters["branches"]] == ["Other Shop"]


def test_cannot_use_another_shops_branch_or_supplier(browser):
    shop_with_parts(browser)
    create_other_shop()
    other = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    other_branch = other.get("/api/stock/filters").json()["branches"][0]["id"]

    response = browser.patch(f"/api/parts/{part_id('BP-001')}", json={"stock": [{"branch_id": other_branch, "quantity": 99}]})

    assert response.status_code == 422
