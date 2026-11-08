import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Branch, Forecast, Part, StockLevel
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

    assert browser.get("/api/stock/summary").json() == {"all": 22, "healthy": 15, "low": 4, "out": 3, "running_out": 0}


def test_empty_shop_has_zero_everywhere(browser):
    set_up_shop(browser)

    assert browser.get("/api/stock/summary").json() == {"all": 0, "healthy": 0, "low": 0, "out": 0, "running_out": 0}
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
    # "Atlas Parts" (the shop's default branch, never used since the file names real branches) is left out.
    assert {row["branch"]: row["quantity"] for row in detail["stock"]} == {"Casablanca": 6, "Rabat": 0}
    assert detail["supplier"]["name"] == "Auto Hall Pièces"
    assert [(s["sold_on"], s["quantity"]) for s in detail["last_sales"]] == [("2026-10-14", 1), ("2026-10-03", 2)]


def test_part_detail_still_shows_the_only_branch_before_anything_is_in_use(browser):
    """A brand-new shop, nothing imported yet (so no branch has any stock or sales at all): its one
    branch must still show, so stock can be set on it -- it isn't filtered away like an unused one
    normally would be once other branches are in use."""
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    with SessionLocal() as db:
        part = Part(organization_id=shop, sku="NEW-1", name="Part NEW-1")
        db.add(part)
        db.commit()
        part_id_ = part.id

    detail = browser.get(f"/api/parts/{part_id_}").json()
    assert {row["branch"]: row["quantity"] for row in detail["stock"]} == {"Atlas Parts": 0}


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


def add_part_with_forecast(
    organization_id: uuid.UUID, sku: str, quantity: int, expected_30d: float | None, min_stock: int = 0,
    sale_price: int | None = None,
) -> uuid.UUID:
    """A part with `quantity` on hand and, when `expected_30d` is given, a 30-day forecast for it."""
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_id == organization_id))
        part = Part(organization_id=organization_id, sku=sku, name=f"Part {sku}", min_stock=min_stock, is_active=True,
                   sale_price=sale_price)
        db.add(part)
        db.flush()
        db.add(StockLevel(organization_id=organization_id, part_id=part.id, branch_id=branch.id, quantity=quantity))
        if expected_30d is not None:
            db.add(
                Forecast(
                    organization_id=organization_id,
                    part_id=part.id,
                    branch_id=branch.id,
                    horizon_days=30,
                    history_last_day=date(2026, 1, 1),
                    demand_type="smooth",
                    method="four_week_average",
                    quantity=expected_30d,
                    low=expected_30d,
                    high=expected_30d,
                    method_wape=None,
                    baseline_wape=None,
                    method_mase=None,
                    baseline_mase=None,
                    backtest_windows=5,
                    reason="test",
                )
            )
        db.commit()
        return part.id


def test_runs_out_in_and_next_30_days(browser):
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    add_part_with_forecast(shop, "SOON-1", quantity=9, expected_30d=30)  # 9 pieces / (1 a day) = 9 days
    add_part_with_forecast(shop, "SAFE-1", quantity=100, expected_30d=10)  # 300 days of cover
    add_part_with_forecast(shop, "NODEM-1", quantity=50, expected_30d=None)  # nothing expected to sell

    soon = next(i for i in parts(browser)["items"] if i["sku"] == "SOON-1")
    safe = next(i for i in parts(browser)["items"] if i["sku"] == "SAFE-1")
    no_demand = next(i for i in parts(browser)["items"] if i["sku"] == "NODEM-1")

    assert (soon["expected_30d"], soon["runs_out_days"]) == (30, 9)
    assert (safe["expected_30d"], safe["runs_out_days"]) == (10, None)
    assert (no_demand["expected_30d"], no_demand["runs_out_days"]) == (0, None)
    assert (soon["status"], safe["status"], no_demand["status"]) == ("running_out", "healthy", "healthy")


def test_running_out_filter_and_stat(browser):
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    add_part_with_forecast(shop, "SOON-1", quantity=9, expected_30d=30)
    add_part_with_forecast(shop, "SAFE-1", quantity=100, expected_30d=10)

    assert browser.get("/api/stock/summary").json()["running_out"] == 1
    assert skus(parts(browser, running_out=True)) == ["SOON-1"]


def test_running_out_leaves_out_parts_already_flagged_low_or_out(browser):
    """A short runway is only worth a separate flag when the minimum stock didn't already catch it."""
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    add_part_with_forecast(shop, "LOW-SOON", quantity=9, expected_30d=30, min_stock=10)  # 9 <= 10: already "low"
    add_part_with_forecast(shop, "OUT-SOON", quantity=0, expected_30d=30)  # already "out"
    add_part_with_forecast(shop, "HEALTHY-SOON", quantity=9, expected_30d=30, min_stock=2)  # 9 > 2: "healthy"

    assert browser.get("/api/stock/summary").json()["running_out"] == 1
    assert skus(parts(browser, running_out=True)) == ["HEALTHY-SOON"]

    items = {item["sku"]: item for item in parts(browser)["items"]}
    assert items["LOW-SOON"]["status"] == "low"  # out of stock and low stock still win
    assert items["OUT-SOON"]["status"] == "out"
    assert items["HEALTHY-SOON"]["status"] == "running_out"  # amber, not green, even though it's above its minimum


def test_running_out_status_shows_on_the_part_panel_and_outranks_healthy_in_sort(browser):
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    running_out_id = add_part_with_forecast(shop, "SOON-1", quantity=9, expected_30d=30, min_stock=2)
    add_part_with_forecast(shop, "SAFE-1", quantity=100, expected_30d=10, min_stock=2)

    detail = browser.get(f"/api/parts/{running_out_id}").json()
    assert detail["status"] == "running_out"

    ordered = parts(browser, sort="status")["items"]
    statuses = [item["status"] for item in ordered if item["sku"] in ("SOON-1", "SAFE-1")]
    assert statuses == ["running_out", "healthy"]  # running_out is more urgent than healthy


def test_sort_by_runs_out_days_puts_the_soonest_first(browser):
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    add_part_with_forecast(shop, "SOON-1", quantity=9, expected_30d=30)
    add_part_with_forecast(shop, "SAFE-1", quantity=100, expected_30d=10)
    add_part_with_forecast(shop, "NODEM-1", quantity=50, expected_30d=None)

    ordered = skus(parts(browser, sort="runs_out_days"))

    assert ordered[0] == "SOON-1"  # nulls (no urgent cover date) sort last, either direction


def test_urgent_filter_and_sort_for_the_today_page(browser):
    """Out of stock first, then whichever runs out soonest, then the most money at stake. Healthy
    and inactive parts are left out, even though one of them would otherwise sort first."""
    set_up_shop(browser)
    shop = browser.get("/api/auth/me").json()["organization"]["id"]
    add_part_with_forecast(shop, "OUT-CHEAP", quantity=0, expected_30d=10, sale_price=100)
    add_part_with_forecast(shop, "OUT-PRICEY", quantity=0, expected_30d=10, sale_price=9000)
    add_part_with_forecast(shop, "LOW-SOON", quantity=9, expected_30d=30, min_stock=10)  # low, runs out in 9 days
    add_part_with_forecast(shop, "LOW-LATER", quantity=9, expected_30d=9, min_stock=10)  # low, runs out in 30 days
    add_part_with_forecast(shop, "HEALTHY-1", quantity=100, expected_30d=10)  # not urgent

    urgent = parts(browser, urgent=True, sort="urgency")
    assert skus(urgent) == ["OUT-PRICEY", "OUT-CHEAP", "LOW-SOON", "LOW-LATER"]
    assert {item["status"] for item in urgent["items"]} == {"out", "low"}
