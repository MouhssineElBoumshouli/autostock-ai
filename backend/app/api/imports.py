"""Excel/CSV import in steps: preview (columns), check (what would happen), save (all or nothing).

The browser sends the file again at each step, so nothing half-done is kept on the server.
"""

import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit import record_change
from app.auth.permissions import require_role
from app.db import get_session
from app.imports.fields import FIELDS, ImportKind, check_mapping
from app.imports.matching import suggest_field
from app.imports.parts_import import plan_parts, save_parts
from app.imports.plan import Summary
from app.imports.reading import MAX_FILE_BYTES, Table, read_table
from app.imports.sales_import import plan_sales, save_sales
from app.imports.values import normalize_header, show_cell
from app.models import ImportMapping, User

router = APIRouter(prefix="/api/imports")
can_import = require_role("owner", "manager")

SAMPLE_ROWS = 5
PROBLEMS_SHOWN = 200


class FieldOut(BaseModel):
    key: str
    required: bool


class ColumnOut(BaseModel):
    index: int
    header: str
    samples: list[str]


class PreviewOut(BaseModel):
    file_name: str
    row_count: int
    columns: list[ColumnOut]
    fields: list[FieldOut]
    mapping: dict[int, str]  # pre-filled from the shop's last import of this kind


class ProblemOut(BaseModel):
    row: int
    messages: list[str]


class SummaryOut(BaseModel):
    file_name: str
    counts: dict[str, int]
    new_suppliers: list[str]
    new_branches: list[str]
    problems: list[ProblemOut]  # the first 200
    problem_count: int


@router.post("/preview")
async def preview(
    file: UploadFile,
    kind: ImportKind = Form(),
    user: User = Depends(can_import),
    db: Session = Depends(get_session),
) -> PreviewOut:
    table, file_name = await _read(file)
    remembered = db.scalar(
        select(ImportMapping.mapping).where(
            ImportMapping.organization_id == user.organization_id, ImportMapping.kind == kind
        )
    ) or {}
    return PreviewOut(
        file_name=file_name,
        row_count=len(table.rows),
        columns=[
            ColumnOut(index=i, header=header, samples=[show_cell(cells[i]) for _, cells in table.rows[:SAMPLE_ROWS]])
            for i, header in enumerate(table.headers)
        ],
        fields=[FieldOut(key=field.key, required=field.required) for field in FIELDS[kind]],
        mapping=_suggest_mapping(kind, table.headers, remembered),
    )


def _suggest_mapping(kind: ImportKind, headers: list[str], remembered: dict[str, str]) -> dict[int, str]:
    """Column -> field: from the shop's own last import first, then a free local guess from the
    header text for whatever is left. The person sees every one of these in the Match step and can
    change it before anything is checked or saved; nothing here is ever applied by itself.
    """
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for i, header in enumerate(headers):
        field = remembered.get(normalize_header(header))
        if field:
            mapping[i] = field
            used.add(field)
    for i, header in enumerate(headers):
        if i in mapping:
            continue
        field = suggest_field(header, kind)
        if field and field not in used:
            mapping[i] = field
            used.add(field)
    return mapping


@router.post("/check")
async def check(
    file: UploadFile,
    kind: ImportKind = Form(),
    mapping: str = Form(),
    user: User = Depends(can_import),
    db: Session = Depends(get_session),
) -> SummaryOut:
    table, file_name = await _read(file)
    columns = check_mapping(kind, _parse_mapping(mapping), len(table.headers))
    plan = _plan(db, kind, user, table, columns)
    return _summary_out(file_name, plan.summary)


@router.post("/save")
async def save(
    file: UploadFile,
    kind: ImportKind = Form(),
    mapping: str = Form(),
    user: User = Depends(can_import),
    db: Session = Depends(get_session),
) -> SummaryOut:
    """Saves every good row in one transaction: if anything fails, nothing is saved."""
    table, file_name = await _read(file)
    by_column = _parse_mapping(mapping)
    columns = check_mapping(kind, by_column, len(table.headers))

    # One import at a time per shop, so two people can't import the same parts at once.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:shop, 0))"), {"shop": str(user.organization_id)})
    plan = _plan(db, kind, user, table, columns)
    if kind == "parts":
        save_parts(db, user.organization_id, plan)
    else:
        save_sales(db, user.organization_id, plan)

    _remember_mapping(db, user, kind, table, by_column)
    record_change(
        db,
        user,
        "import.saved",
        "import",
        uuid.uuid4(),
        after={
            "kind": kind,
            "file_name": file_name,
            **plan.summary.counts,
            "new_suppliers": len(plan.summary.new_suppliers),
            "new_branches": len(plan.summary.new_branches),
        },
    )
    db.commit()
    return _summary_out(file_name, plan.summary)


async def _read(file: UploadFile) -> tuple[Table, str]:
    content = await file.read(MAX_FILE_BYTES + 1)
    file_name = file.filename or "file"
    return read_table(content, file_name), file_name


def _parse_mapping(raw: str) -> dict[int, str]:
    try:
        data = json.loads(raw)
        return {int(column): str(field) for column, field in data.items() if field}
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(422, "The column matching doesn't fit this file. Upload it again.") from None


def _plan(db: Session, kind: ImportKind, user: User, table: Table, columns: dict[str, int]):
    if kind == "parts":
        return plan_parts(db, user.organization_id, table, columns)
    return plan_sales(db, user.organization_id, table, columns)


def _remember_mapping(db: Session, user: User, kind: ImportKind, table: Table, by_column: dict[int, str]) -> None:
    """Adds this import's column matching to what is remembered, without losing headers from past imports
    that aren't in this file (e.g. a supplier's file has different columns than the shop's own export).
    """
    this_import = {normalize_header(table.headers[column]): field for column, field in by_column.items()}
    row = db.scalar(
        select(ImportMapping).where(ImportMapping.organization_id == user.organization_id, ImportMapping.kind == kind)
    )
    if row is None:
        db.add(ImportMapping(organization_id=user.organization_id, kind=kind, mapping=this_import))
    else:
        row.mapping = {**row.mapping, **this_import}


def _summary_out(file_name: str, summary: Summary) -> SummaryOut:
    return SummaryOut(
        file_name=file_name,
        counts=summary.counts,
        new_suppliers=summary.new_suppliers,
        new_branches=summary.new_branches,
        problems=[ProblemOut(row=p.row, messages=p.messages) for p in summary.problems[:PROBLEMS_SHOWN]],
        problem_count=len(summary.problems),
    )
