from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from app.db import SessionLocal
from app.exports import build
from app.models import Branch, Part, SaleLine
from tests.helpers import add_member, audit_rows, member_with_own_password, set_up_shop
from tests.import_helpers import PARTS_MAPPING, SALES_MAPPING, send


def test_owner_downloads_an_xlsx_with_one_sheet_per_kind(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)
    send(browser, "save", "sales", "sales_fr_messy.csv", SALES_MAPPING)

    response = browser.get("/api/exports/data")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in response.headers["content-disposition"]
    workbook = load_workbook(BytesIO(response.content))
    # The shop's language is French by default, so every sheet name is French too.
    assert workbook.sheetnames == [
        "Lisez-moi", "Pièces", "Ventes", "Commandes fournisseurs", "Fournisseurs", "Succursales",
        "Pièces équivalentes", "Utilisateurs", "Journal d’activité",
    ]
    read_me = workbook["Lisez-moi"]
    assert read_me["A1"].value == "AutoStock AI -- toutes les données de votre magasin"
    assert read_me["B3"].value == "Atlas Parts"

    parts = workbook["Pièces"]
    assert parts["A1"].value == "Référence"
    # 22 new parts from the fixture file (7 rows are left out as problems).
    assert parts.max_row == 23

    sales = workbook["Ventes"]
    assert sales["A1"].value == "Date"
    assert sales.max_row > 1

    assert audit_rows("data.exported")


def test_a_part_s_money_comes_back_as_a_real_number_not_centimes(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)

    workbook = load_workbook(BytesIO(browser.get("/api/exports/data").content))
    parts = workbook["Pièces"]
    header = [cell.value for cell in parts[1]]
    by_sku = {row[0]: dict(zip(header, row)) for row in parts.iter_rows(min_row=2, values_only=True)}

    bp001 = by_sku["BP-001"]
    assert bp001["Prix d’achat"] == 180.0  # not 18000 centimes
    assert bp001["Prix de vente"] == 320.0


def test_stock_is_broken_down_by_branch_and_totalled(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)

    workbook = load_workbook(BytesIO(browser.get("/api/exports/data").content))
    parts = workbook["Pièces"]
    header = [cell.value for cell in parts[1]]
    assert "Stock à Casablanca" in header
    assert "Stock à Rabat" in header
    by_sku = {row[0]: dict(zip(header, row)) for row in parts.iter_rows(min_row=2, values_only=True)}
    bp001 = by_sku["BP-001"]
    assert bp001["Quantité en stock"] == bp001["Stock à Casablanca"] + bp001["Stock à Rabat"]
    assert bp001["Quantité en stock"] == 6


def test_a_manager_cannot_download_the_shop_s_data(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")

    response = manager.get("/api/exports/data")

    assert response.status_code == 403


def _sales_in_the_database() -> list[tuple]:
    with SessionLocal() as db:
        rows = db.execute(
            select(SaleLine.sold_on, Part.sku, SaleLine.quantity, SaleLine.unit_price, Branch.name)
            .join(Part, Part.id == SaleLine.part_id).join(Branch, Branch.id == SaleLine.branch_id)
        ).all()
    return sorted(
        (datetime.combine(day, datetime.min.time()), sku, quantity, None if price is None else price / 100, branch)
        for day, sku, quantity, price, branch in rows
    )


def test_every_sales_line_comes_back_exactly_as_stored(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)
    send(browser, "save", "sales", "sales_fr_messy.csv", SALES_MAPPING)
    with SessionLocal() as db:  # a line without a price leaves its cell empty
        db.query(SaleLine).filter(SaleLine.id == db.scalar(select(SaleLine.id).limit(1))).update({"unit_price": None})
        db.commit()

    workbook = load_workbook(BytesIO(browser.get("/api/exports/data").content))
    sales = list(workbook["Ventes"].iter_rows(min_row=2, values_only=True))

    assert sorted(sales) == _sales_in_the_database()
    assert any(row[3] is None for row in sales)
    assert [row[0] for row in sales] == sorted(row[0] for row in sales)  # oldest first


def test_sales_too_many_for_one_sheet_are_spread_over_several(browser, monkeypatch):
    monkeypatch.setattr(build, "SALES_PER_SHEET", 4)
    set_up_shop(browser)
    send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)
    send(browser, "save", "sales", "sales_fr_messy.csv", SALES_MAPPING)
    expected = _sales_in_the_database()

    workbook = load_workbook(BytesIO(browser.get("/api/exports/data").content))
    sheet_count = -(-len(expected) // 4)
    sales_sheets = [f"Ventes {n}" for n in range(1, sheet_count + 1)]
    assert sheet_count > 1 and workbook.sheetnames[2:2 + sheet_count] == sales_sheets
    assert workbook.sheetnames[2 + sheet_count] == "Commandes fournisseurs"
    rows = []
    for name in sales_sheets:
        assert workbook[name]["A1"].value == "Date"
        rows += list(workbook[name].iter_rows(min_row=2, values_only=True))
        assert workbook[name].max_row - 1 <= 4
    assert sorted(rows) == expected
    read_me = {row[0]: row[1] for row in workbook["Lisez-moi"].iter_rows(values_only=True) if row and row[0]}
    assert [read_me[name] for name in sales_sheets] == [4] * (sheet_count - 1) + [len(expected) - 4 * (sheet_count - 1)]
