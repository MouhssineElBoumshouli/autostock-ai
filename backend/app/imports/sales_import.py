"""Import of "Sales history" files: adds sales lines for parts that already exist."""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.imports.plan import NameBook, Problem, Summary, cells_by_field, main_branch
from app.imports.reading import Table
from app.imports.values import ValueProblem, clean_sku, clean_text, parse_date, parse_money, parse_whole_number
from app.models import Branch, Part, SaleLine


@dataclass
class SaleRow:
    sold_on: date
    part_id: uuid.UUID
    branch: str | None
    quantity: int
    unit_price: int | None


@dataclass
class SalesPlan:
    summary: Summary
    rows: list[SaleRow]
    branches: NameBook


def plan_sales(db: Session, organization_id: uuid.UUID, table: Table, columns: dict[str, int]) -> SalesPlan:
    part_ids = dict(db.execute(select(Part.sku, Part.id).where(Part.organization_id == organization_id)).all())
    branches = NameBook(db, Branch, organization_id)
    default_branch = main_branch(db, organization_id)

    good: list[SaleRow] = []
    problems: list[Problem] = []
    for number, cells in cells_by_field(table, columns):
        messages: list[str] = []
        row = _clean_row(cells, part_ids, messages)
        if messages:
            problems.append(Problem(row=number, messages=messages))
        else:
            good.append(row)

    # Lines already in the database (same day, part, branch, quantity and price) are not added twice,
    # so importing the same file again does not double the sales.
    new_rows, already = _skip_already_imported(db, organization_id, good, branches, default_branch.id)
    for row in new_rows:
        if row.branch:
            branches.note(row.branch)

    summary = Summary(
        counts={"new_sales": len(new_rows), "already_imported": already, "problem_rows": len(problems)},
        new_branches=sorted(branches.new_names.values()),
        problems=problems,
    )
    return SalesPlan(summary=summary, rows=new_rows, branches=branches)


def save_sales(db: Session, organization_id: uuid.UUID, plan: SalesPlan) -> None:
    plan.branches.create_new(db)
    default_branch = main_branch(db, organization_id)
    db.add_all(
        SaleLine(
            organization_id=organization_id,
            sold_on=row.sold_on,
            part_id=row.part_id,
            branch_id=plan.branches.id_of(row.branch) if row.branch else default_branch.id,
            quantity=row.quantity,
            unit_price=row.unit_price,
        )
        for row in plan.rows
    )


def _clean_row(cells: dict, part_ids: dict[str, uuid.UUID], messages: list[str]) -> SaleRow:
    def attempt(parse, *args):
        try:
            return parse(*args)
        except ValueProblem as problem:
            messages.append(str(problem))
            return None

    sold_on = attempt(parse_date, cells.get("date"))
    if sold_on is None and not messages:
        messages.append("Date is missing")

    sku = clean_sku(cells.get("sku"))
    part_id = part_ids.get(sku) if sku else None
    if not sku:
        messages.append("SKU is missing")
    elif part_id is None:
        messages.append(f"SKU {sku} is not in your parts. Import it with “Parts and stock” first")

    quantity_problems = len(messages)
    quantity = attempt(parse_whole_number, cells.get("quantity"), "Quantity")
    if quantity is None and len(messages) == quantity_problems:
        messages.append("Quantity is missing")
    elif quantity == 0:
        messages.append("Quantity can't be 0")

    unit_price = attempt(parse_money, cells.get("unit_price"), "Unit price") if "unit_price" in cells else None
    return SaleRow(
        sold_on=sold_on,
        part_id=part_id,
        branch=clean_text(cells.get("branch")),
        quantity=quantity or 0,
        unit_price=unit_price,
    )


def _skip_already_imported(db, organization_id, rows: list[SaleRow], branches: NameBook, default_branch_id):
    if not rows:
        return [], 0

    def key(sold_on, part_id, branch_id, quantity, unit_price):
        return (sold_on, part_id, branch_id, quantity, unit_price)

    first, last = min(r.sold_on for r in rows), max(r.sold_on for r in rows)
    in_database = Counter(
        {
            key(*line[:5]): line[5]
            for line in db.execute(
                select(
                    SaleLine.sold_on,
                    SaleLine.part_id,
                    SaleLine.branch_id,
                    SaleLine.quantity,
                    SaleLine.unit_price,
                    func.count(),
                )
                .where(SaleLine.organization_id == organization_id, SaleLine.sold_on.between(first, last))
                .group_by(SaleLine.sold_on, SaleLine.part_id, SaleLine.branch_id, SaleLine.quantity, SaleLine.unit_price)
            ).all()
        }
    )
    new_rows, already = [], 0
    for row in rows:
        branch_id = branches.existing_id(row.branch) if row.branch else default_branch_id
        row_key = key(row.sold_on, row.part_id, branch_id, row.quantity, row.unit_price)
        if branch_id is not None and in_database[row_key] > 0:
            in_database[row_key] -= 1
            already += 1
        else:
            new_rows.append(row)
    return new_rows, already
