"""The trial files are what a new shop brings on day one: they must import with no help and no
problem row, carry the seed's data, and never say where they come from."""

import zipfile
from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.demo.trial_files import shop_sku, write_files
from app.models import Part, PartEquivalent, SaleLine, StockLevel, Supplier
from tests.helpers import set_up_shop
from tests.import_helpers import send

LAST_DAY = date(2026, 6, 30)


def total(model, column, shop_id) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.coalesce(func.sum(column), 0)).where(model.organization_id == shop_id))


def number_of(model, shop_id) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(model.organization_id == shop_id))


def bring_in(browser, kind: str, path) -> dict:
    content = path.read_bytes()
    preview = send(browser, "preview", kind, path.name, content=content).json()
    mapping = {int(column): field for column, field in preview["mapping"].items()}
    assert len(mapping) == len(preview["columns"])  # every column recognised by the app itself
    summary = send(browser, "save", kind, path.name, mapping, content=content).json()
    assert summary["counts"]["problem_rows"] == 0, summary["problems"]
    return summary


def test_seed_part_numbers_lose_their_name():
    assert shop_sku("DEMO-0042") == "AL-0042"


def test_trial_files_import_cleanly_into_an_empty_shop(browser, tmp_path):
    with SessionLocal() as db:
        seed, _ = create_demo_shop(db, LAST_DAY, parts_count=800, history_days=90, seed=7)
        db.commit()
        seed_id = seed.id
        counts = write_files(db, seed_id, tmp_path)

    set_up_shop(browser)
    shop_id = browser.get("/api/auth/me").json()["organization"]["id"]
    parts = bring_in(browser, "parts", tmp_path / "Pièces.xlsx")
    sales = bring_in(browser, "sales", tmp_path / "Ventes.csv")
    again = send(browser, "check", "sales", "Ventes.xlsx", {0: "date", 1: "sku", 2: "quantity", 3: "unit_price", 4: "branch"},
                 content=(tmp_path / "Ventes.xlsx").read_bytes()).json()
    equivalents = bring_in(browser, "equivalents", tmp_path / "Équivalences.xlsx")

    assert parts["counts"]["new_parts"] == number_of(Part, seed_id) == 800
    assert sales["counts"]["new_sales"] == counts["Ventes"] == number_of(SaleLine, seed_id)
    assert again["counts"]["already_imported"] == counts["Ventes"]  # the CSV and the Excel file say the same
    assert equivalents["counts"]["new_equivalents"] == counts["Équivalences.xlsx"]
    assert number_of(StockLevel, shop_id) == number_of(StockLevel, seed_id)
    assert number_of(PartEquivalent, shop_id) == counts["Équivalences.xlsx"]
    assert total(StockLevel, StockLevel.quantity, shop_id) == total(StockLevel, StockLevel.quantity, seed_id)
    assert total(SaleLine, SaleLine.quantity, shop_id) == total(SaleLine, SaleLine.quantity, seed_id)


def test_no_file_says_it_is_made_up(tmp_path):
    with SessionLocal() as db:
        seed, _ = create_demo_shop(db, LAST_DAY, parts_count=25, history_days=90, seed=7)
        db.commit()
        write_files(db, seed.id, tmp_path)

    for path in tmp_path.iterdir():
        if path.suffix == ".csv":
            assert "demo" not in path.read_text(encoding="cp1252").lower()
            continue
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                assert b"demo" not in archive.read(name).lower(), (path.name, name)


def suppliers_delivery(shop_id) -> dict[str, tuple[int | None, str | None]]:
    with SessionLocal() as db:
        rows = db.execute(select(Supplier.name, Supplier.delivery_days, Supplier.delivery_source)
                          .where(Supplier.organization_id == shop_id))
        return {name: (days, source) for name, days, source in rows}


def without_delivery_column(path) -> bytes:
    """The Pièces file as the shop had it before: no delivery-time column."""
    book = load_workbook(path)
    sheet = book.active
    column = next(cell.column for cell in sheet[1] if cell.value == "Délai de livraison (jours)")
    sheet.delete_cols(column)
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def test_the_parts_file_gives_each_supplier_its_real_delivery_time(browser, tmp_path):
    with SessionLocal() as db:
        seed, _ = create_demo_shop(db, LAST_DAY, parts_count=60, history_days=90, seed=7)
        db.commit()
        seed_id = seed.id
        write_files(db, seed_id, tmp_path)
    set_up_shop(browser)
    shop_id = browser.get("/api/auth/me").json()["organization"]["id"]

    summary = bring_in(browser, "parts", tmp_path / "Pièces.xlsx")

    expected = {name: days for name, (days, _) in suppliers_delivery(seed_id).items()}
    assert summary["counts"]["delivery_times"] == len(expected)
    assert suppliers_delivery(shop_id) == {name: (days, "file") for name, days in expected.items()}


def test_the_same_parts_file_again_with_delivery_times_only_fills_them_in(browser, tmp_path):
    with SessionLocal() as db:
        seed, _ = create_demo_shop(db, LAST_DAY, parts_count=60, history_days=90, seed=7)
        db.commit()
        seed_id = seed.id
        write_files(db, seed_id, tmp_path)
    expected = {name: days for name, (days, _) in suppliers_delivery(seed_id).items()}
    set_up_shop(browser)
    shop_id = browser.get("/api/auth/me").json()["organization"]["id"]
    old_file = without_delivery_column(tmp_path / "Pièces.xlsx")
    first = send(browser, "preview", "parts", "Pièces.xlsx", content=old_file).json()
    send(browser, "save", "parts", "Pièces.xlsx", {int(k): v for k, v in first["mapping"].items()}, content=old_file)
    assert set(suppliers_delivery(shop_id).values()) == {(None, None)}
    with SessionLocal() as db:  # stock moved since the first import: an order came in
        level = db.scalar(select(StockLevel).where(StockLevel.organization_id == shop_id).limit(1))
        level.quantity += 40
        moved_id, moved_to = level.id, level.quantity
        db.commit()
    parts_before, stock_before = number_of(Part, shop_id), number_of(StockLevel, shop_id)

    again = bring_in(browser, "parts", tmp_path / "Pièces.xlsx")

    assert again["counts"]["delivery_only"] == 1
    assert again["counts"]["new_parts"] == again["counts"]["updated_parts"] == 0
    assert again["new_suppliers"] == [] and again["new_branches"] == []
    assert suppliers_delivery(shop_id) == {name: (days, "file") for name, days in expected.items()}
    assert number_of(Part, shop_id) == parts_before and number_of(StockLevel, shop_id) == stock_before
    with SessionLocal() as db:
        assert db.get(StockLevel, moved_id).quantity == moved_to  # not put back to the file's number

    third = bring_in(browser, "parts", tmp_path / "Pièces.xlsx")  # imported again: a normal update

    assert third["counts"]["delivery_only"] == 0 and third["counts"]["updated_parts"] == 1
    assert number_of(Part, shop_id) == parts_before and len(suppliers_delivery(shop_id)) == len(expected)
    with SessionLocal() as db:
        assert db.get(StockLevel, moved_id).quantity == moved_to - 40
