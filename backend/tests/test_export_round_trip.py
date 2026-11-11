"""Proves the exported data really leaves whole: export the demo shop, feed its own Parts and
Sales sheets back through our own import screen into a fresh, empty shop, and check that what
came out the other end matches -- same counts, same stock and sales totals.
"""

from datetime import date
from io import BytesIO

from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import DEMO_OWNER_EMAIL, add_demo_owner, create_demo_shop
from app.models import Part, SaleLine, StockLevel
from tests.helpers import logged_in_browser, new_browser, set_up_shop
from tests.import_helpers import send

LAST_DAY = date(2026, 6, 30)


def _single_sheet_bytes(workbook, sheet_name: str) -> bytes:
    """One sheet of a workbook, alone in its own file: read_table() only ever looks at the first
    sheet, same as a shop opening one tab of a spreadsheet to send us."""
    source = workbook[sheet_name]
    single = Workbook()
    sheet = single.active
    for row in source.iter_rows(values_only=True):
        sheet.append(row)
    buffer = BytesIO()
    single.save(buffer)
    return buffer.getvalue()


def _stock_total(organization_id) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.coalesce(func.sum(StockLevel.quantity), 0)).where(StockLevel.organization_id == organization_id)
        )


def _sales_total(organization_id) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.coalesce(func.sum(SaleLine.quantity), 0)).where(SaleLine.organization_id == organization_id)
        )


def _part_count(organization_id) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Part).where(Part.organization_id == organization_id))


def test_demo_shop_s_export_imports_cleanly_into_a_fresh_shop():
    with SessionLocal() as db:
        demo_shop, _buckets = create_demo_shop(db, LAST_DAY, parts_count=25, history_days=90, seed=7)
        password = add_demo_owner(db, demo_shop)
        db.commit()
        demo_shop_id = demo_shop.id

    demo_browser = logged_in_browser(DEMO_OWNER_EMAIL, password)
    export_response = demo_browser.get("/api/exports/data")
    assert export_response.status_code == 200, export_response.text
    workbook = load_workbook(BytesIO(export_response.content))

    parts_file = _single_sheet_bytes(workbook, "Pièces")  # the demo shop's language is French
    sales_file = _single_sheet_bytes(workbook, "Ventes")

    destination = new_browser()
    set_up_shop(destination, email="owner@newshop.ma")

    parts_preview = send(destination, "preview", "parts", "export-parts.xlsx", content=parts_file).json()
    parts_mapping = {int(k): v for k, v in parts_preview["mapping"].items()}
    # The whole point: our own export's headers are recognised without the person touching anything.
    assert parts_mapping == {0: "sku", 1: "name", 2: "brand", 3: "category", 4: "oem_reference",
                              5: "unit_cost", 6: "sale_price", 7: "min_stock", 8: "pack_size",
                              9: "supplier", 10: "quantity"}
    parts_summary = send(destination, "save", "parts", "export-parts.xlsx", parts_mapping, content=parts_file).json()
    assert parts_summary["counts"]["problem_rows"] == 0

    sales_preview = send(destination, "preview", "sales", "export-sales.xlsx", content=sales_file).json()
    sales_mapping = {int(k): v for k, v in sales_preview["mapping"].items()}
    assert sales_mapping == {0: "date", 1: "sku", 2: "quantity", 3: "unit_price", 4: "branch"}
    sales_summary = send(destination, "save", "sales", "export-sales.xlsx", sales_mapping, content=sales_file).json()
    assert sales_summary["counts"]["problem_rows"] == 0

    destination_id = destination.get("/api/auth/me").json()["organization"]["id"]

    assert _part_count(destination_id) == _part_count(demo_shop_id) == 25
    assert _stock_total(destination_id) == _stock_total(demo_shop_id)
    assert _sales_total(destination_id) == _sales_total(demo_shop_id)
