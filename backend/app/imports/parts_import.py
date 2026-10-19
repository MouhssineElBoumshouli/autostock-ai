"""Import of "Parts and stock" files: creates or updates parts, sets stock on hand per branch."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports.plan import NameBook, Problem, Summary, cells_by_field, find_duplicates, label, main_branch
from app.imports.reading import Table
from app.imports.values import (
    ValueProblem,
    clean_sku,
    clean_text,
    parse_money,
    parse_whole_number,
)
from app.models import Branch, Part, StockLevel, Supplier

TEXT_FIELDS = ("name", "brand", "category", "oem_reference")
MONEY_FIELDS = ("unit_cost", "sale_price")


@dataclass
class PartRow:
    sku: str
    values: dict  # part columns found in the file (empty cells left out, so they don't erase data)
    supplier: str | None
    branch: str | None
    quantity: int | None


@dataclass
class PartsPlan:
    summary: Summary
    rows: list[PartRow]
    suppliers: NameBook
    branches: NameBook


def plan_parts(db: Session, organization_id: uuid.UUID, table: Table, columns: dict[str, int]) -> PartsPlan:
    parts = {
        part.sku: part for part in db.scalars(select(Part).where(Part.organization_id == organization_id))
    }
    suppliers = NameBook(db, Supplier, organization_id)
    branches = NameBook(db, Branch, organization_id)
    default_branch = main_branch(db, organization_id)
    stock = {
        (level.part_id, level.branch_id): level.quantity
        for level in db.scalars(select(StockLevel).where(StockLevel.organization_id == organization_id))
    }

    cleaned: dict[int, PartRow] = {}
    problems: dict[int, list[str]] = {}
    for number, cells in cells_by_field(table, columns):
        messages: list[str] = []
        row = _clean_row(cells, messages)
        if row.sku and "name" not in row.values and row.sku not in parts:
            messages.append("Name is missing (needed for a new part)")
        if messages:
            problems[number] = messages
        if row.sku:
            cleaned[number] = row

    for number, rows in find_duplicates({n: r.sku for n, r in cleaned.items()}).items():
        problems.setdefault(number, []).append(f"Same SKU twice in the file (rows {', '.join(map(str, rows))})")

    good = [row for number, row in cleaned.items() if number not in problems]
    counts = {"new_parts": 0, "updated_parts": 0, "unchanged_parts": 0, "problem_rows": len(problems)}
    for row in good:
        if row.supplier:
            suppliers.note(row.supplier)
        if row.branch:
            branches.note(row.branch)
        existing = parts.get(row.sku)
        if existing is None:
            counts["new_parts"] += 1
        elif _changes(existing, row, suppliers, branches, default_branch, stock):
            counts["updated_parts"] += 1
        else:
            counts["unchanged_parts"] += 1

    summary = Summary(
        counts=counts,
        new_suppliers=sorted(suppliers.new_names.values()),
        new_branches=sorted(branches.new_names.values()),
        problems=[Problem(row=number, messages=problems[number]) for number in sorted(problems)],
    )
    return PartsPlan(summary=summary, rows=good, suppliers=suppliers, branches=branches)


def save_parts(db: Session, organization_id: uuid.UUID, plan: PartsPlan) -> None:
    plan.suppliers.create_new(db)
    plan.branches.create_new(db)
    default_branch = main_branch(db, organization_id)
    parts = {
        part.sku: part for part in db.scalars(select(Part).where(Part.organization_id == organization_id))
    }
    levels = {
        (level.part_id, level.branch_id): level
        for level in db.scalars(select(StockLevel).where(StockLevel.organization_id == organization_id))
    }

    for row in plan.rows:
        part = parts.get(row.sku)
        if part is None:
            part = Part(organization_id=organization_id, sku=row.sku, min_stock=0, is_active=True)
            db.add(part)
            parts[row.sku] = part
        for key, value in row.values.items():
            setattr(part, key, value)
        if row.supplier:
            part.supplier_id = plan.suppliers.id_of(row.supplier)
        db.flush()

        if row.quantity is not None:
            branch_id = plan.branches.id_of(row.branch) if row.branch else default_branch.id
            level = levels.get((part.id, branch_id))
            if level is None:
                level = StockLevel(organization_id=organization_id, part_id=part.id, branch_id=branch_id)
                db.add(level)
                levels[(part.id, branch_id)] = level
            level.quantity = row.quantity


def _clean_row(cells: dict, messages: list[str]) -> PartRow:
    def attempt(parse, *args):
        try:
            return parse(*args)
        except ValueProblem as problem:
            messages.append(str(problem))
            return None

    sku = clean_sku(cells.get("sku"))
    if not sku:
        messages.append("SKU is missing")
    values = {}
    for key in TEXT_FIELDS:
        if key in cells and (text := clean_text(cells[key])):
            values[key] = text
    for key in MONEY_FIELDS:
        if key in cells and (money := attempt(parse_money, cells[key], label("parts", key))) is not None:
            values[key] = money
    if "min_stock" in cells:
        minimum = attempt(parse_whole_number, cells["min_stock"], "Minimum stock")
        if minimum is not None:
            values["min_stock"] = minimum
    if "pack_size" in cells:  # optional: an empty cell leaves the pack size as it was (1 for a new part)
        pack = attempt(parse_whole_number, cells["pack_size"], "Pack size")
        if pack == 0:
            messages.append("Pack size must be at least 1")
        elif pack is not None:
            values["pack_size"] = pack
    quantity = attempt(parse_whole_number, cells.get("quantity"), "Quantity") if "quantity" in cells else None
    return PartRow(
        sku=sku or "",
        values=values,
        supplier=clean_text(cells.get("supplier")),
        branch=clean_text(cells.get("branch")),
        quantity=quantity,
    )


def _changes(part: Part, row: PartRow, suppliers: NameBook, branches: NameBook, default_branch, stock) -> bool:
    if any(getattr(part, key) != value for key, value in row.values.items()):
        return True
    if row.supplier and part.supplier_id != suppliers.existing_id(row.supplier):
        return True
    if row.quantity is not None:
        branch_id = branches.existing_id(row.branch) if row.branch else default_branch.id
        return branch_id is None or stock.get((part.id, branch_id)) != row.quantity
    return False
