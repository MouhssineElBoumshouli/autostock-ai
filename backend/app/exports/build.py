"""Builds the "download all my data" .xlsx: one sheet per kind of data, in the owner's own
language, real Excel numbers and dates (not centimes, not text). Streamed with openpyxl's
write-only mode, so a big shop (tens of thousands of parts, years of sales) doesn't run out of
memory: nothing is held in a worksheet object, each row goes straight into the zip file as it's
written (openpyxl docs: https://openpyxl.readthedocs.io/en/stable/optimized.html).
"""

import uuid
from datetime import UTC, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.worksheet._write_only import WriteOnlyWorksheet as Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.exports import labels
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
    SaleLine,
    StockLevel,
    Supplier,
    User,
)

BOLD = Font(bold=True)


def build_export(db: Session, organization_id: uuid.UUID) -> tuple[BytesIO, str]:
    """Returns the workbook's bytes and a file name, e.g. "AutoStock - Atlas Parts - 2026-10-29.xlsx"."""
    organization = db.get_one(Organization, organization_id)
    language = labels.for_language(organization.language)
    names = labels.SHEET_NAMES[language]

    workbook = Workbook(write_only=True)
    read_me = workbook.create_sheet(names["read_me"])
    counts = {
        "parts": _write_parts(workbook.create_sheet(names["parts"]), db, organization_id, language),
        "sales": _write_sales(workbook.create_sheet(names["sales"]), db, organization_id, language),
        "purchase_orders": _write_purchase_orders(workbook.create_sheet(names["purchase_orders"]), db, organization_id, language),
        "suppliers": _write_suppliers(workbook.create_sheet(names["suppliers"]), db, organization_id, language),
        "branches": _write_branches(workbook.create_sheet(names["branches"]), db, organization_id, language),
        "equivalent_parts": _write_equivalents(workbook.create_sheet(names["equivalent_parts"]), db, organization_id, language),
        "users": _write_users(workbook.create_sheet(names["users"]), db, organization_id, language),
        "activity_log": _write_activity(workbook.create_sheet(names["activity_log"]), db, organization_id, language),
    }
    _write_read_me(read_me, organization, language, counts)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    file_name = f"AutoStock - {organization.name} - {to_shop_time(datetime.now(UTC)).strftime('%Y-%m-%d')}.xlsx"
    return buffer, file_name


def _header(sheet: Worksheet, texts: list[str]) -> None:
    cells = []
    for text in texts:
        cell = WriteOnlyCell(sheet, value=text)
        cell.font = BOLD
        cells.append(cell)
    sheet.append(cells)


def _write_read_me(sheet: Worksheet, organization: Organization, language: str, counts: dict[str, int]) -> None:
    words = labels.READ_ME[language]
    names = labels.SHEET_NAMES[language]
    sheet.append([words["title"]])
    sheet.append([])
    sheet.append([words["shop_name"], organization.name])
    sheet.append([words["export_date"], to_shop_time(datetime.now(UTC))])
    sheet.append([])
    sheet.append([words["row_counts"]])
    for kind, count in counts.items():
        sheet.append([names[kind], count])


def _write_parts(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    words = field_labels(language, "parts")
    branches = db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ).all()
    stock_at = labels.STOCK_AT[language]
    _header(
        sheet,
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
    count = 0
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
        count += 1
    return count


def _write_sales(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    words = field_labels(language, "sales")
    _header(sheet, [words["date"], words["sku"], words["quantity"], words["unit_price"], words["branch"]])
    count = 0
    rows = db.execute(
        select(SaleLine.sold_on, Part.sku, SaleLine.quantity, SaleLine.unit_price, Branch.name)
        .join(Part, Part.id == SaleLine.part_id)
        .join(Branch, Branch.id == SaleLine.branch_id)
        .where(SaleLine.organization_id == organization_id)
        .order_by(SaleLine.sold_on)
    ).yield_per(5000)
    for sold_on, sku, quantity, unit_price, branch_name in rows:
        sheet.append([sold_on, sku, quantity, _money(unit_price), branch_name])
        count += 1
    return count


def _write_purchase_orders(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.PURCHASE_ORDER_HEADERS[language])
    status_names = labels.PURCHASE_ORDER_STATUS[language]
    count = 0
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
        count += 1
    return count


def _write_suppliers(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.SUPPLIER_HEADERS[language])
    count = 0
    for supplier in db.scalars(
        select(Supplier).where(Supplier.organization_id == organization_id).order_by(Supplier.name)
    ):
        sheet.append([supplier.name, supplier.phone, supplier.email, supplier.delivery_days])
        count += 1
    return count


def _write_branches(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.BRANCH_HEADERS[language])
    count = 0
    for branch in db.scalars(
        select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.created_at)
    ):
        sheet.append([branch.name])
        count += 1
    return count


def _write_equivalents(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.EQUIVALENT_HEADERS[language])
    source_names = labels.EQUIVALENT_SOURCE[language]
    part_a, part_b = aliased(Part), aliased(Part)
    count = 0
    rows = db.execute(
        select(part_a.sku, part_a.name, part_b.sku, part_b.name, PartEquivalent.source, User.name, PartEquivalent.created_at)
        .join(part_a, part_a.id == PartEquivalent.part_a_id)
        .join(part_b, part_b.id == PartEquivalent.part_b_id)
        .outerjoin(User, User.id == PartEquivalent.created_by_user_id)
        .where(PartEquivalent.organization_id == organization_id)
    )
    for sku_a, name_a, sku_b, name_b, source, linked_by, linked_on in rows:
        sheet.append([sku_a, name_a, sku_b, name_b, source_names.get(source, source), linked_by, to_shop_time(linked_on)])
        count += 1
    return count


def _write_users(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.USER_HEADERS[language])
    role_names = labels.ROLE_NAMES[language]
    yes_no = labels.YES_NO[language]
    count = 0
    for user in db.scalars(
        select(User).where(User.organization_id == organization_id).order_by(User.created_at)
    ):
        sheet.append(
            [user.name, user.email, role_names.get(user.role, user.role), yes_no[user.is_active], to_shop_time(user.last_login_at)]
        )
        count += 1
    return count


def _write_activity(sheet: Worksheet, db: Session, organization_id: uuid.UUID, language: str) -> int:
    _header(sheet, labels.ACTIVITY_HEADERS[language])
    system_person = labels.SYSTEM_PERSON[language]
    count = 0
    rows = db.execute(
        select(AuditLog.created_at, User.name, AuditLog.action, AuditLog.before, AuditLog.after)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at)
    ).yield_per(5000)
    for created_at, actor_name, action, before, after in rows:
        sheet.append([to_shop_time(created_at), actor_name or system_person, action, _change_text(before, after)])
        count += 1
    return count


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
