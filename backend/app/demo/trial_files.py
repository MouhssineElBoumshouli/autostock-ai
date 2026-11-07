"""Writes the realistic shop's data as the files a real shop would bring on its first day, to try
the app the way a new customer does: an empty app, first setup, then these files.

Run inside Docker:  docker compose exec api python -m app.demo.trial_files
Writes into the trial/ folder next to this project (git-ignored):
  Pièces.xlsx        one row per part and branch: stock, supplier and its delivery time, prices,
                     pack size, minimum, OEM
  Ventes.csv         24 months of sales, the way Excel in French saves a CSV
  Ventes.xlsx        the same sales as an Excel file
  Équivalences.xlsx  which parts are the same part under another brand

The same made-up data as the seed of app/demo/demo_shop.py, built in a transaction that is then
undone: the database stays exactly as it was.
"""

import csv
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.demo.demo_shop import create_demo_shop
from app.demo.production_guard import refuse_demo_in_production
from app.exports.xlsx import Workbook
from app.models import Branch, Part, SaleLine, StockLevel, Supplier

SKU_START = "AL-"  # the seed's part numbers carry its own name: a real shop's don't
PARTS_HEADERS = [
    "Référence", "Désignation", "Marque", "Famille", "Référence OEM", "Fournisseur", "Délai de livraison (jours)", "Prix d'achat", "Prix de vente",
    "Conditionnement", "Stock minimum", "Succursale", "Quantité en stock",
]
SALES_HEADERS = ["Date", "Référence", "Quantité vendue", "Prix unitaire", "Succursale"]
EQUIVALENTS_HEADERS = ["Notre référence", "Référence équivalente"]


def shop_sku(seed_sku: str) -> str:
    return re.sub("^DEMO-", SKU_START, seed_sku)


def dirhams(centimes: int | None) -> float | None:
    return None if centimes is None else centimes / 100


def french_money(centimes: int | None) -> str:
    return "" if centimes is None else f"{centimes / 100:.2f}".replace(".", ",")


def write_files(db: Session, organization_id, folder: Path) -> dict[str, int]:
    """Reads the shop and writes its files. Returns how many rows each has."""
    parts = db.scalars(select(Part).where(Part.organization_id == organization_id).order_by(Part.sku)).all()
    branch_names = dict(db.execute(select(Branch.id, Branch.name).where(Branch.organization_id == organization_id)).all())
    suppliers = {row.id: row for row in db.scalars(select(Supplier).where(Supplier.organization_id == organization_id))}
    stock: dict = defaultdict(list)
    for part_id, branch_id, quantity in db.execute(
        select(StockLevel.part_id, StockLevel.branch_id, StockLevel.quantity).where(StockLevel.organization_id == organization_id)
    ):
        stock[part_id].append((branch_names[branch_id], quantity))
    return {
        "Pièces.xlsx": _write_parts(folder / "Pièces.xlsx", parts, suppliers, stock),
        "Ventes": _write_sales(folder, db, organization_id, parts, branch_names),
        "Équivalences.xlsx": _write_equivalents(folder / "Équivalences.xlsx", parts),
    }


def _write_parts(path: Path, parts: list[Part], suppliers: dict, stock: dict) -> int:
    rows = 0
    with open(path, "wb") as file:
        book = Workbook(file)
        sheet = book.add_sheet("Pièces")
        sheet.header(PARTS_HEADERS)
        for part in parts:
            for branch, quantity in sorted(stock[part.id]):
                sheet.append([
                    shop_sku(part.sku), part.name, part.brand, part.category, part.oem_reference,
                    suppliers[part.supplier_id].name, suppliers[part.supplier_id].delivery_days, dirhams(part.unit_cost), dirhams(part.sale_price),
                    part.pack_size, part.min_stock, branch, quantity,
                ])
                rows += 1
        book.close()
    return rows


def _write_sales(folder: Path, db: Session, organization_id, parts: list[Part], branch_names: dict) -> int:
    skus = {part.id: shop_sku(part.sku) for part in parts}
    lines = db.execute(
        select(SaleLine.sold_on, SaleLine.part_id, SaleLine.quantity, SaleLine.unit_price, SaleLine.branch_id)
        .where(SaleLine.organization_id == organization_id)
        .order_by(SaleLine.sold_on)
    ).yield_per(10_000)
    rows = 0
    with open(folder / "Ventes.csv", "w", encoding="cp1252", newline="") as csv_file, open(folder / "Ventes.xlsx", "wb") as xlsx_file:
        writer = csv.writer(csv_file, delimiter=";")
        writer.writerow(SALES_HEADERS)
        book = Workbook(xlsx_file)
        sheet = book.add_sheet("Ventes")
        sheet.header(SALES_HEADERS)
        for sold_on, part_id, quantity, unit_price, branch_id in lines:
            branch = branch_names[branch_id]
            writer.writerow([f"{sold_on:%d/%m/%Y}", skus[part_id], quantity, french_money(unit_price), branch])
            sheet.append([sold_on, skus[part_id], quantity, dirhams(unit_price), branch])
            rows += 1
        book.close()
    return rows


def _write_equivalents(path: Path, parts: list[Part]) -> int:
    """Each part with the first part of the same OEM number, as a supplier's cross-reference lists them."""
    by_oem: dict[str, list[str]] = defaultdict(list)
    for part in parts:
        by_oem[part.oem_reference].append(shop_sku(part.sku))
    rows = 0
    with open(path, "wb") as file:
        book = Workbook(file)
        sheet = book.add_sheet("Équivalences")
        sheet.header(EQUIVALENTS_HEADERS)
        for skus in by_oem.values():
            for other in skus[1:]:
                sheet.append([skus[0], other])
                rows += 1
        book.close()
    return rows


def main() -> None:
    refuse_demo_in_production()
    started = perf_counter()
    folder = Path(os.environ.get("TRIAL_DIR", "trial"))
    folder.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        shop, _ = create_demo_shop(db, last_day=date.today() - timedelta(days=1))
        db.flush()
        counts = write_files(db, shop.id, folder)
        db.rollback()  # the shop was only needed to write the files
    for name, rows in counts.items():
        print(f"{name}: {rows:,} rows")
    print(f"Written to {folder} in {perf_counter() - started:.0f} s.")


if __name__ == "__main__":
    main()
