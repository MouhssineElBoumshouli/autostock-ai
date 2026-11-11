"""Import of "Sales history" files: adds sales lines for parts that already exist.

The file goes row by row into a temporary table of this transaction, and PostgreSQL does the
rest (lines already saved, adding the new ones): millions of lines never sit in the app's memory.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.imports.plan import (
    ROWS_PER_SEND,
    NameBook,
    ProblemReport,
    Summary,
    cells_by_field,
    copy_cell,
    give_room_to_sort,
    main_branch,
    send_rows,
)
from app.imports.reading import Table
from app.imports.values import ValueProblem, clean_sku, clean_text, parse_date, parse_money, parse_whole_number
from app.models import Branch, Part

ROWS_REMEMBERED = 100_000  # a history repeats the same dates, parts, quantities and prices

# Lines already in the database (same day, part, branch, quantity and price) are not added twice,
# so importing the same file again does not double the sales. Lines the same in the file count one
# by one: 3 same lines against 2 saved ones add 1.
NEW_LINES = """
    SELECT incoming.sold_on, incoming.part_id, incoming.branch_id, incoming.quantity, incoming.unit_price
    FROM (
        SELECT sold_on, part_id, branch_id, quantity, unit_price, row_number() OVER (
                   PARTITION BY sold_on, part_id, branch_id, quantity, unit_price
               ) AS nth
        FROM (
            SELECT line.sold_on, line.part_id, line.quantity, line.unit_price,
                   CASE WHEN line.branch IS NULL THEN CAST(:default_branch AS uuid) ELSE branch.id END AS branch_id
            FROM incoming_sales AS line
            LEFT JOIN branches AS branch ON branch.organization_id = :shop AND lower(branch.name) = line.branch
        ) AS resolved
    ) AS incoming
    LEFT JOIN (
        SELECT sold_on, part_id, branch_id, quantity, unit_price, count(*) AS times
        FROM sale_lines
        WHERE organization_id = :shop AND sold_on BETWEEN :first_day AND :last_day
        GROUP BY sold_on, part_id, branch_id, quantity, unit_price
    ) AS saved
        ON saved.sold_on = incoming.sold_on AND saved.part_id = incoming.part_id AND saved.branch_id = incoming.branch_id
        AND saved.quantity = incoming.quantity AND saved.unit_price IS NOT DISTINCT FROM incoming.unit_price
    WHERE incoming.nth > coalesce(saved.times, 0)
"""


@dataclass
class SalesPlan:
    summary: Summary
    branches: NameBook
    first_day: date | None
    last_day: date | None


def plan_sales(db: Session, organization_id: uuid.UUID, table: Table, columns: dict[str, int]) -> SalesPlan:
    give_room_to_sort(db)
    db.execute(text(
        """CREATE TEMP TABLE incoming_sales (
               sold_on date NOT NULL, part_id uuid NOT NULL, branch text, quantity integer NOT NULL, unit_price bigint
           ) ON COMMIT DROP"""
    ))
    part_ids = {sku: str(part_id) for sku, part_id in db.execute(select(Part.sku, Part.id).where(Part.organization_id == organization_id))}
    branches = NameBook(db, Branch, organization_id)
    default_branch = main_branch(db, organization_id)

    report = ProblemReport()
    first_day, last_day = None, None
    good_rows = 0
    waiting: list[str] = []
    for number, cells in cells_by_field(table, columns):
        messages: list[str] = []
        sold_on, part_id, branch, quantity, unit_price = _clean_row(cells, part_ids, messages)
        if messages:
            report.add(number, messages, table.sheet)
            continue
        good_rows += 1
        first_day = sold_on if first_day is None or sold_on < first_day else first_day
        last_day = sold_on if last_day is None or sold_on > last_day else last_day
        if branch:
            branches.note(branch)
        waiting.append(f"{sold_on}\t{part_id}\t{copy_cell(branch.lower() if branch else None)}\t{quantity}\t{copy_cell(unit_price)}\n")
        if len(waiting) == ROWS_PER_SEND:
            send_rows(db, "incoming_sales", waiting)
            waiting = []
    send_rows(db, "incoming_sales", waiting)

    new_lines = 0
    if good_rows:
        db.execute(text("ANALYZE incoming_sales"))
        new_lines = db.scalar(
            text(f"SELECT count(*) FROM ({NEW_LINES}) AS new_lines"),
            _query_values(organization_id, default_branch.id, first_day, last_day),
        )
    if not new_lines:
        branches.new_names.clear()

    summary = Summary(
        counts={"new_sales": new_lines, "already_imported": good_rows - new_lines, "problem_rows": report.count},
        new_branches=sorted(branches.new_names.values()),
        problems=report.first,
        problem_count=report.count,
    )
    return SalesPlan(summary=summary, branches=branches, first_day=first_day, last_day=last_day)


def save_sales(db: Session, organization_id: uuid.UUID, plan: SalesPlan) -> None:
    if not plan.summary.counts["new_sales"]:
        return
    plan.branches.create_new(db)
    default_branch = main_branch(db, organization_id)
    # Row ids in increasing order from a random start: PostgreSQL adds them at the end of its id
    # index instead of all over it. Reference checks stay on: this is a real shop's data.
    db.execute(
        text(
            f"""INSERT INTO sale_lines (id, created_at, organization_id, sold_on, part_id, branch_id, quantity, unit_price)
                SELECT CAST(:id_start || lpad(to_hex(row_number() OVER ()), 16, '0') AS uuid), now(), :shop,
                       sold_on, part_id, branch_id, quantity, unit_price
                FROM ({NEW_LINES}) AS new_lines"""
        ),
        {**_query_values(organization_id, default_branch.id, plan.first_day, plan.last_day), "id_start": secrets.token_hex(8)},
    )


def analyze_sales(db: Session) -> None:
    """Tells PostgreSQL's planner about the new lines now, not whenever its own helper gets to it:
    the first pages after a big import would otherwise choose slow ways to read them."""
    db.execute(text("ANALYZE sale_lines"))


def _query_values(organization_id: uuid.UUID, default_branch_id: uuid.UUID, first_day: date | None, last_day: date | None) -> dict:
    return {"shop": organization_id, "default_branch": default_branch_id, "first_day": first_day, "last_day": last_day}


@lru_cache(maxsize=ROWS_REMEMBERED, typed=True)
def _read_date(value) -> tuple[date | None, str | None]:
    return _attempt(parse_date, value)


@lru_cache(maxsize=ROWS_REMEMBERED, typed=True)
def _read_quantity(value) -> tuple[int | None, str | None]:
    return _attempt(parse_whole_number, value, "Quantity")


@lru_cache(maxsize=ROWS_REMEMBERED, typed=True)
def _read_price(value) -> tuple[int | None, str | None]:
    return _attempt(parse_money, value, "Unit price")


def _attempt(parse, *args) -> tuple:
    try:
        return parse(*args), None
    except ValueProblem as problem:
        return None, str(problem)


def _clean_row(cells: dict, part_ids: dict[str, str], messages: list[str]) -> tuple:
    sold_on, problem = _read_date(cells.get("date"))
    if problem:
        messages.append(problem)
    elif sold_on is None:
        messages.append("Date is missing")

    sku = clean_sku(cells.get("sku"))
    part_id = part_ids.get(sku) if sku else None
    if not sku:
        messages.append("SKU is missing")
    elif part_id is None:
        messages.append(f"SKU {sku} is not in your parts. Import it with “Parts and stock” first")

    quantity, problem = _read_quantity(cells.get("quantity"))
    if problem:
        messages.append(problem)
    elif quantity is None:
        messages.append("Quantity is missing")
    elif quantity == 0:
        messages.append("Quantity can't be 0")

    unit_price = None
    if "unit_price" in cells:
        unit_price, problem = _read_price(cells["unit_price"])
        if problem:
            messages.append(problem)
    return sold_on, part_id, clean_text(cells.get("branch")), quantity, unit_price
