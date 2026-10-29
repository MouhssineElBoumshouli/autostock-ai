from io import BytesIO

from openpyxl import load_workbook

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
