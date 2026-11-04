"""Import of "Parts and stock" files: creates or updates parts, sets stock on hand per branch.

A part may come on several rows, one per branch, each with that branch's stock. The file goes row
by row into a temporary table of this transaction, and PostgreSQL compares and saves it all at
once: a list of millions of rows never sits in the app's memory.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.imports.plan import (
    PROBLEMS_KEPT,
    ROWS_PER_SEND,
    NameBook,
    Problem,
    ProblemReport,
    Summary,
    cells_by_field,
    copy_cell,
    give_room_to_sort,
    label,
    main_branch,
    send_rows,
)
from app.imports.reading import Table
from app.imports.values import ValueProblem, clean_sku, clean_text, parse_money, parse_whole_number
from app.models import Branch, Part, Supplier

TEXT_FIELDS = ("name", "brand", "category", "oem_reference")
MONEY_FIELDS = ("unit_cost", "sale_price")
NUMBER_FIELDS = ("min_stock", "pack_size")
PART_COLUMNS = (*TEXT_FIELDS, *MONEY_FIELDS, *NUMBER_FIELDS)
ROWS_NAMED = 6  # how many row numbers a "same SKU" message lists
INCOMING = (
    f"incoming_parts (row_number, sheet, sku, {', '.join(PART_COLUMNS)}, supplier, branch, quantity, has_problem)"
)

# Good rows, each with its branch and supplier found by name.
GOOD_ROWS = """
    SELECT line.*, known.id AS part_id,
           CASE WHEN line.branch IS NULL THEN CAST(:default_branch AS uuid) ELSE branch.id END AS branch_id,
           supplier.id AS supplier_id
    FROM incoming_parts AS line
    LEFT JOIN parts AS known ON known.organization_id = :shop AND known.sku = line.sku
    LEFT JOIN branches AS branch ON branch.organization_id = :shop AND lower(branch.name) = line.branch
    LEFT JOIN suppliers AS supplier ON supplier.organization_id = :shop AND lower(supplier.name) = line.supplier
    WHERE NOT line.has_problem
"""

# One line per part. Its rows never disagree (see _mark_repeated_skus), so max() is what they say,
# and an empty cell on one row doesn't hide what another row says.
ONE_LINE_PER_PART = f"""
    SELECT sku, part_id, {", ".join(f"max({column}) AS {column}" for column in PART_COLUMNS)},
           (array_agg(supplier_id) FILTER (WHERE supplier_id IS NOT NULL))[1] AS supplier_id
    FROM ({GOOD_ROWS}) AS good GROUP BY sku, part_id
"""

COUNT_CHANGES = f"""
    WITH good AS MATERIALIZED ({GOOD_ROWS}),
    changed AS (
        SELECT DISTINCT good.sku
        FROM good JOIN parts AS part ON part.id = good.part_id
        LEFT JOIN stock_levels AS level ON level.part_id = part.id AND level.branch_id = good.branch_id
        WHERE {" OR ".join(f"(good.{c} IS NOT NULL AND good.{c} IS DISTINCT FROM part.{c})" for c in PART_COLUMNS)}
           OR (good.supplier IS NOT NULL AND good.supplier_id IS DISTINCT FROM part.supplier_id)
           OR (good.quantity IS NOT NULL AND good.quantity IS DISTINCT FROM level.quantity)
    )
    SELECT (SELECT count(DISTINCT sku) FROM good WHERE part_id IS NULL) AS new_parts,
           (SELECT count(*) FROM changed) AS updated_parts,
           (SELECT count(DISTINCT sku) FROM good WHERE part_id IS NOT NULL) AS known_parts
"""

UPDATE_PARTS = f"""
    UPDATE parts AS part
    SET {", ".join(f"{c} = coalesce(line.{c}, part.{c})" for c in PART_COLUMNS)},
        supplier_id = coalesce(line.supplier_id, part.supplier_id)
    FROM ({ONE_LINE_PER_PART}) AS line
    WHERE part.id = line.part_id
"""

INSERT_PARTS = f"""
    INSERT INTO parts (id, created_at, organization_id, sku, name, brand, category, oem_reference, unit_cost,
                       sale_price, min_stock, pack_size, supplier_id, is_active)
    SELECT gen_random_uuid(), now(), :shop, sku, name, brand, category, oem_reference, unit_cost, sale_price,
           coalesce(min_stock, 0), coalesce(pack_size, 1), supplier_id, true
    FROM ({ONE_LINE_PER_PART}) AS line
    WHERE part_id IS NULL
"""

SET_STOCK = f"""
    INSERT INTO stock_levels (id, created_at, organization_id, part_id, branch_id, quantity)
    SELECT gen_random_uuid(), now(), :shop, part.id, good.branch_id, good.quantity
    FROM ({GOOD_ROWS}) AS good
    JOIN parts AS part ON part.organization_id = :shop AND part.sku = good.sku
    WHERE good.quantity IS NOT NULL
    ON CONFLICT (part_id, branch_id) DO UPDATE SET quantity = excluded.quantity
"""

# A SKU may repeat for another branch, with the same details. Anything else can't be trusted: every
# row concerned is marked, and left out.
MARK_SAME_BRANCH_TWICE = """
    UPDATE incoming_parts AS line SET same_branch_rows = twice.rows
    FROM (
        SELECT sku, branch, (array_agg(row_number ORDER BY place))[1:7] AS rows
        FROM incoming_parts GROUP BY sku, branch HAVING count(*) > 1
    ) AS twice
    WHERE line.sku = twice.sku AND line.branch IS NOT DISTINCT FROM twice.branch
"""
MARK_DIFFERENT_DETAILS = f"""
    UPDATE incoming_parts AS line SET different_rows = disagree.rows
    FROM (
        SELECT sku, (array_agg(row_number ORDER BY place))[1:7] AS rows
        FROM incoming_parts GROUP BY sku
        HAVING {" OR ".join(f"count(DISTINCT {c}) > 1" for c in (*PART_COLUMNS, "supplier"))}
    ) AS disagree
    WHERE line.sku = disagree.sku
"""


@dataclass
class PartsPlan:
    summary: Summary
    suppliers: NameBook
    branches: NameBook
    has_good_rows: bool


def plan_parts(db: Session, organization_id: uuid.UUID, table: Table, columns: dict[str, int]) -> PartsPlan:
    give_room_to_sort(db)
    _create_incoming_table(db)
    known_skus = set(db.scalars(select(Part.sku).where(Part.organization_id == organization_id)))
    suppliers = NameBook(db, Supplier, organization_id)
    branches = NameBook(db, Branch, organization_id)
    default_branch = main_branch(db, organization_id)

    report = ProblemReport()
    waiting: list[str] = []
    for number, cells in cells_by_field(table, columns):
        messages: list[str] = []
        sku, values, supplier, branch, quantity = _clean_row(cells, messages)
        if sku and "name" not in values and sku not in known_skus:
            messages.append("Name is missing (needed for a new part)")
        if messages:
            report.add(number, messages, table.sheet)
        if not sku:
            continue
        if not messages:
            if supplier:
                suppliers.note(supplier)
            if branch:
                branches.note(branch)
        waiting.append(_copy_line(number, table.sheet, sku, values, supplier, branch, quantity, bool(messages)))
        if len(waiting) == ROWS_PER_SEND:
            send_rows(db, INCOMING, waiting)
            waiting = []
    send_rows(db, INCOMING, waiting)

    db.execute(text("ANALYZE incoming_parts"))
    _mark_repeated_skus(db, report)
    good = db.scalar(text("SELECT count(*) FROM incoming_parts WHERE NOT has_problem"))
    _forget_names_only_on_problem_rows(db, suppliers, "supplier")
    _forget_names_only_on_problem_rows(db, branches, "branch")
    plain = {"shop": organization_id, "default_branch": default_branch.id}
    new_parts, updated, known = db.execute(text(COUNT_CHANGES), plain).one()

    summary = Summary(
        counts={"new_parts": new_parts, "updated_parts": updated, "unchanged_parts": known - updated, "problem_rows": report.count},
        new_suppliers=sorted(suppliers.new_names.values()),
        new_branches=sorted(branches.new_names.values()),
        problems=report.first,
        problem_count=report.count,
    )
    return PartsPlan(summary=summary, suppliers=suppliers, branches=branches, has_good_rows=good > 0)


def save_parts(db: Session, organization_id: uuid.UUID, plan: PartsPlan) -> None:
    if not plan.has_good_rows:
        return
    plan.suppliers.create_new(db)
    plan.branches.create_new(db)
    values = {"shop": organization_id, "default_branch": main_branch(db, organization_id).id}
    db.execute(text(UPDATE_PARTS), values)
    db.execute(text(INSERT_PARTS), values)
    db.execute(text(SET_STOCK), values)


def analyze_parts(db: Session) -> None:
    """Tells PostgreSQL's planner about the new rows now (the sales import looks up every part)."""
    db.execute(text("ANALYZE parts"))
    db.execute(text("ANALYZE stock_levels"))


def _create_incoming_table(db: Session) -> None:
    db.execute(text(
        """CREATE TEMP TABLE incoming_parts (
               place serial, row_number integer NOT NULL, sheet text, sku text NOT NULL, name text, brand text,
               category text, oem_reference text, unit_cost bigint, sale_price bigint, min_stock integer,
               pack_size integer, supplier text, branch text, quantity integer, has_problem boolean NOT NULL,
               same_branch_rows integer[], different_rows integer[]
           ) ON COMMIT DROP"""
    ))


def _copy_line(number: int, sheet, sku: str, values: dict, supplier, branch, quantity, has_problem: bool) -> str:
    cells = [
        number, sheet, sku, *(values.get(column) for column in PART_COLUMNS),
        supplier.lower() if supplier else None, branch.lower() if branch else None, quantity, has_problem,
    ]
    return "\t".join(copy_cell(cell) for cell in cells) + "\n"


def _mark_repeated_skus(db: Session, report: ProblemReport) -> None:
    db.execute(text(MARK_SAME_BRANCH_TWICE))
    db.execute(text(MARK_DIFFERENT_DETAILS))
    marked = "(same_branch_rows IS NOT NULL OR different_rows IS NOT NULL)"
    report.count += db.scalar(text(f"SELECT count(*) FROM incoming_parts WHERE NOT has_problem AND {marked}"))
    first_marked = db.execute(
        text(f"SELECT row_number, sheet, same_branch_rows, different_rows FROM incoming_parts WHERE {marked} ORDER BY place LIMIT {PROBLEMS_KEPT}")
    ).all()
    db.execute(text(f"UPDATE incoming_parts SET has_problem = true WHERE {marked}"))

    kept = {(problem.sheet, problem.row): problem for problem in report.first}
    for number, sheet, same_branch_rows, different_rows in first_marked:
        problem = kept.setdefault((sheet, number), Problem(number, [], sheet))
        if same_branch_rows:
            problem.messages.append(f"Same SKU twice in the file (rows {_named(same_branch_rows)})")
        if different_rows:
            problem.messages.append(f"Same SKU with different details (rows {_named(different_rows)})")
    report.first = sorted(kept.values(), key=lambda problem: (problem.sheet or "", problem.row))[:PROBLEMS_KEPT]


def _named(rows: list[int]) -> str:
    return ", ".join(map(str, rows[:ROWS_NAMED])) + (", ..." if len(rows) > ROWS_NAMED else "")


def _forget_names_only_on_problem_rows(db: Session, names: NameBook, column: str) -> None:
    if names.new_names:
        used = set(db.scalars(text(f"SELECT DISTINCT {column} FROM incoming_parts WHERE NOT has_problem AND {column} IS NOT NULL")))
        names.new_names = {lower: name for lower, name in names.new_names.items() if lower in used}


def _clean_row(cells: dict, messages: list[str]) -> tuple[str, dict[str, Any], str | None, str | None, int | None]:
    def attempt(parse, *args):
        try:
            return parse(*args)
        except ValueProblem as problem:
            messages.append(str(problem))
            return None

    sku = clean_sku(cells.get("sku"))
    if not sku:
        messages.append("SKU is missing")
    values: dict[str, Any] = {}
    for key in TEXT_FIELDS:
        if key in cells and (text_value := clean_text(cells[key])):
            values[key] = text_value
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
    return sku or "", values, clean_text(cells.get("supplier")), clean_text(cells.get("branch")), quantity
