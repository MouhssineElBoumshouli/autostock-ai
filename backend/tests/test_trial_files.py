"""The trial files are what a new shop brings on day one: they must import with no help and no
problem row, carry the seed's data, and never say where they come from."""

import zipfile
from datetime import date

from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.demo.trial_files import shop_sku, write_files
from app.models import Part, PartEquivalent, SaleLine, StockLevel
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
