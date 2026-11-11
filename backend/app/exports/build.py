"""Builds the "download all my data" .xlsx: one sheet per kind of data, in the owner's own
language, real Excel numbers and dates (not centimes, not text). Each row goes straight into the
file as it's written (app/exports/xlsx.py), so a big shop doesn't run out of memory.

Sales can be tens of millions of lines, more than one Excel sheet holds (1,048,576 rows): they
are spread over "Sales 1", "Sales 2"... of SALES_PER_SHEET lines each. PostgreSQL writes each
sales row's XML itself, so 20 million lines take a few minutes instead of an hour.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import IO

from sqlalchemy import select, text
from sqlalchemy.orm import Session, aliased

from app.exports import labels
from app.exports.xlsx import DATE_STYLE, EXCEL_DAY_ZERO, Sheet, Workbook
from app.imports.fields import field_labels
from app.shop_day import to_shop_time
from app.models import (
    AuditLog,
    Branch,
    Organization,
    Part,
    PartEquivalent,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLevel,
    Supplier,
    User,
)

SALES_PER_SHEET = 1_000_000  # under Excel's 1,048,576 rows, and a round number


def build_export(db: Session, organization_id: uuid.UUID, file: IO[bytes]) -> str:
    """Writes the workbook into `file` and returns its name, e.g. "AutoStock - Atlas Parts - 2026-10-29.xlsx"."""
    organization = db.get_one(Organization, organization_id)
    language = labels.for_language(organization.language)
    names = labels.SHEET_NAMES[language]

    book = Workbook(file)
    _write_parts(book.add_sheet(names["parts"]), db, organization_id, language)
    _write_sales(book, names["sales"], db, organization_id, language)
    _write_purchase_orders(book.add_sheet(names["purchase_orders"]), db, organization_id, language)
    _write_suppliers(book.add_sheet(names["suppliers"]), db, organization_id, language)
    _write_branches(book.add_sheet(names["branches"]), db, organization_id, language)
    _write_equivalents(book.add_sheet(names["equivalent_parts"]), db, organization_id, language)
    _write_users(book.add_sheet(names["users"]), db, organization_id, language)
    _write_activity(book.add_sheet(names["activity_log"]), db, organization_id, language)
    data_sheets = list(book.sheets)
    _write_read_me(book.add_sheet(names["read_me"], first=True), organization, language, data_sheets)
    book.close()
    return f"AutoStock - {organization.name} - {to_shop_time(datetime.now(UTC)).strftime('%Y-%m-%d')}.xlsx"


def _write_read_me(sheet: Sheet, organization: Organization, language: str, data_sheets: list[Sheet]) -> None:
    words = labels.READ_ME[language]
    sheet.append([words["title"]])
    sheet.append([])
    sheet.append([words["shop_name"], organization.name])
    sheet.append([words["export_date"], to_shop_time(datetime.now(UTC))])
    sheet.append([])
    sheet.append([words["row_counts"]])
    for data_sheet in data_sheets:
        sheet.append([data_sheet.name, data_sheet.row_count - 1])  # not counting the header


def _write_parts(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    words = field_labels(language, "parts")
    branches = db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ).all()
    stock_at = labels.STOCK_AT[language]
    sheet.header(
        [
            words["sku"], words["name"], words["brand"], words["category"], words["oem_reference"],
            words["unit_cost"], words["sale_price"], words["min_stock"], words["pack_size"], words["supplier"],
            words["quantity"],
        ]
        + [f"{stock_at} {branch.name}" for branch in branches],
    )
    branch_index = {branch.id: i for i, branch in enumerate(branches)}
    # Stock per part, all at once (a shop has far fewer stock levels than years of sales): one row
    # per (part, branch), so a 50,000-part shop with 3 branches is still only ~150,000 small rows.
    stock_by_part: dict[uuid.UUID, list[int]] = {}
    for part_id, branch_id, quantity in db.execute(
        select(StockLevel.part_id, StockLevel.branch_id, StockLevel.quantity).where(StockLevel.organization_id == organization_id)
    ):
        if branch_id in branch_index:
            stock_by_part.setdefault(part_id, [0] * len(branches))[branch_index[branch_id]] = quantity

    supplier_name = aliased(Supplier)
    rows = db.execute(
        select(Part, supplier_name.name)
        .outerjoin(supplier_name, supplier_name.id == Part.supplier_id)
        .where(Part.organization_id == organization_id)
        .order_by(Part.sku)
    ).yield_per(2000)
    for part, supplier_name_value in rows:
        per_branch = stock_by_part.get(part.id) or [0] * len(branches)
        sheet.append(
            [
                part.sku, part.name, part.brand, part.category, part.oem_reference,
                _money(part.unit_cost), _money(part.sale_price), part.min_stock, part.pack_size, supplier_name_value,
                sum(per_branch),
            ]
            + per_branch
        )


def _write_sales(book: Workbook, name: str, db: Session, organization_id: uuid.UUID, language: str) -> None:
    """One sheet if the sales fit, else "Sales 1", "Sales 2"... of SALES_PER_SHEET lines each,
    oldest day first.

    PostgreSQL turns each sales line into an Excel row itself, one day at a time: a day's lines are
    read straight from the (shop, day) index, with no sorting of millions of rows. The part number
    and the branch are shared texts: export_text_numbers says where each one is."""
    words = field_labels(language, "sales")
    header = [words["date"], words["sku"], words["quantity"], words["unit_price"], words["branch"]]
    shop = {"shop": organization_id}
    db.execute(text("CREATE TEMPORARY TABLE export_text_numbers (id uuid PRIMARY KEY, number int) ON COMMIT DROP"))
    _number_texts(book, db, "SELECT id, sku FROM parts WHERE organization_id = :shop", shop)
    _number_texts(book, db, "SELECT id, name FROM branches WHERE organization_id = :shop", shop)
    first_day, last_day = db.execute(text("SELECT min(sold_on), max(sold_on) FROM sale_lines WHERE organization_id = :shop"), shop).one()

    sheets = [book.add_sheet(name)]
    sheets[0].header(header)
    with db.connection().connection.driver_connection.cursor() as cursor:
        for day in _days(first_day, last_day):
            # organization_id is a UUID and day a date: nothing to escape
            with cursor.copy(f"""
                COPY (
                    SELECT concat(
                        '<row><c s="{DATE_STYLE}"><v>{(day - EXCEL_DAY_ZERO).days}</v></c>',
                        '<c t="s"><v>', part.number, '</v></c>',
                        '<c><v>', sale.quantity, '</v></c>',
                        CASE WHEN sale.unit_price IS NULL THEN '<c/>'
                             ELSE concat('<c><v>', (sale.unit_price / 100.0)::float8, '</v></c>') END,
                        '<c t="s"><v>', branch.number, '</v></c></row>'
                    )
                    FROM sale_lines AS sale
                    JOIN export_text_numbers AS part ON part.id = sale.part_id
                    JOIN export_text_numbers AS branch ON branch.id = sale.branch_id
                    WHERE sale.organization_id = '{organization_id}' AND sale.sold_on = '{day}'
                ) TO STDOUT""") as rows:
                for row in rows:  # one sales line, already XML
                    if sheets[-1].row_count > SALES_PER_SHEET:
                        sheets.append(book.add_sheet(f"{name} {len(sheets) + 1}"))
                        sheets[-1].header(header)
                    sheets[-1].append_xml(row)
    if len(sheets) > 1:
        sheets[0].name = f"{name} 1"


def _number_texts(book: Workbook, db: Session, query: str, params: dict) -> None:
    """Adds each row's text to the shared texts, and its number to export_text_numbers."""
    rows = db.execute(text(query), params).all()
    first = book.add_texts([row[1] for row in rows])
    numbers = [{"id": row_id, "number": first + n} for n, (row_id, _) in enumerate(rows)]
    if numbers:
        db.execute(text("INSERT INTO export_text_numbers VALUES (:id, :number)"), numbers)
    db.execute(text("ANALYZE export_text_numbers"))  # so PostgreSQL knows how big it is


def _days(first: date | None, last: date | None) -> list[date]:
    return [] if first is None else [first + timedelta(days=n) for n in range((last - first).days + 1)]


def _write_purchase_orders(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.PURCHASE_ORDER_HEADERS[language])
    status_names = labels.PURCHASE_ORDER_STATUS[language]
    rows = db.execute(
        select(
            PurchaseOrder.order_number, Supplier.name, PurchaseOrder.status, PurchaseOrder.sent_at,
            PurchaseOrder.received_at, Part.sku, Part.name, Branch.name, PurchaseOrderLine.quantity,
            PurchaseOrderLine.received_quantity, PurchaseOrderLine.unit_cost,
        )
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .join(Part, Part.id == PurchaseOrderLine.part_id)
        .join(Branch, Branch.id == PurchaseOrderLine.branch_id)
        .where(PurchaseOrder.organization_id == organization_id)
        .order_by(PurchaseOrder.order_number)
    )
    for order_number, supplier, status, sent_at, received_at, sku, name, branch, quantity, received, unit_cost in rows:
        sheet.append(
            [
                order_number, supplier, status_names.get(status, status), to_shop_time(sent_at), to_shop_time(received_at),
                sku, name, branch, quantity, received, _money(unit_cost),
            ]
        )


def _write_suppliers(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.SUPPLIER_HEADERS[language])
    for supplier in db.scalars(
        select(Supplier).where(Supplier.organization_id == organization_id).order_by(Supplier.name)
    ):
        sheet.append([supplier.name, supplier.phone, supplier.email, supplier.delivery_days])


def _write_branches(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.BRANCH_HEADERS[language])
    for branch in db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ):
        sheet.append([branch.name])


def _write_equivalents(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.EQUIVALENT_HEADERS[language])
    source_names = labels.EQUIVALENT_SOURCE[language]
    part_a, part_b = aliased(Part), aliased(Part)
    rows = db.execute(
        select(part_a.sku, part_a.name, part_b.sku, part_b.name, PartEquivalent.source, User.name, PartEquivalent.created_at)
        .join(part_a, part_a.id == PartEquivalent.part_a_id)
        .join(part_b, part_b.id == PartEquivalent.part_b_id)
        .outerjoin(User, User.id == PartEquivalent.created_by_user_id)
        .where(PartEquivalent.organization_id == organization_id)
    )
    for sku_a, name_a, sku_b, name_b, source, linked_by, linked_on in rows:
        sheet.append([sku_a, name_a, sku_b, name_b, source_names.get(source, source), linked_by, to_shop_time(linked_on)])


def _write_users(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.USER_HEADERS[language])
    role_names = labels.ROLE_NAMES[language]
    yes_no = labels.YES_NO[language]
    for user in db.scalars(
        select(User).where(User.organization_id == organization_id).order_by(User.created_at)
    ):
        sheet.append(
            [user.name, user.email, role_names.get(user.role, user.role), yes_no[user.is_active], to_shop_time(user.last_login_at)]
        )


def _write_activity(sheet: Sheet, db: Session, organization_id: uuid.UUID, language: str) -> None:
    sheet.header(labels.ACTIVITY_HEADERS[language])
    system_person = labels.SYSTEM_PERSON[language]
    rows = db.execute(
        select(AuditLog.created_at, User.name, AuditLog.action, AuditLog.before, AuditLog.after)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at)
    ).yield_per(5000)
    for created_at, actor_name, action, before, after in rows:
        sheet.append([to_shop_time(created_at), actor_name or system_person, action, _change_text(before, after)])


def _money(centimes: int | None) -> float | None:
    """Centimes -> a real number in the shop's currency, e.g. 1250 -> 12.5."""
    return None if centimes is None else centimes / 100


def _change_text(before: dict | None, after: dict | None) -> str:
    """A compact "field: before -> after" line, so the Activity log sheet is still readable
    without re-reading the whole app: this is a raw data dump, not the Activity page's sentences
    (those are built in the browser, in the person's language, from the same before/after)."""
    before, after = before or {}, after or {}
    keys = list(after.keys()) or list(before.keys())
    parts = []
    for key in keys:
        if key not in before:
            parts.append(f"{key}: {after[key]}")
        elif key not in after:
            parts.append(f"{key} ({before[key]})")
        elif before[key] != after[key]:
            parts.append(f"{key}: {before[key]} -> {after[key]}")
    return "; ".join(parts)
