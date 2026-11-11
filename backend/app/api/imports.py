"""Excel/CSV import in steps: upload (columns), check (what would happen), save (all or nothing).

The file stays on the server from upload to save, and the shop's import is a row in import_jobs:
checking and saving run in the background, and the screen follows them, also after a page reload.
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.alerts.run import run_alerts_now
from app.auth.permissions import require_role
from app.db import SessionLocal, get_session, utc_now
from app.forecast.run import run_forecasts_apart
from app.imports import jobs
from app.imports.fields import FIELDS, ImportKind, check_mapping
from app.imports.matching import looks_like_sales_file, suggest_field
from app.imports.reading import Table, open_table
from app.imports.sample_files import build_sample_file
from app.imports.values import normalize_header, show_cell
from app.models import ImportJob, ImportMapping, Organization, User
from app.stock_outs import record_stock_outs_now

router = APIRouter(prefix="/api/imports")
can_import = require_role("owner", "manager")

SAMPLE_ROWS = 5
ALREADY_RUNNING = "Another import is still running. Wait for it to finish."
GONE = "This import is no longer here. Upload the file again."
SHOW_FINISHED_FOR = timedelta(hours=1)  # then the Import screen is ready for the next file
KEEP_UNFINISHED_FOR = timedelta(hours=24)


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
    # A "parts" file with a date and a quantity column, but no name: probably sales history.
    # Defaults to False so a preview saved before this existed still reads back fine.
    looks_like_sales: bool = False


class ProblemOut(BaseModel):
    row: int
    sheet: str | None
    messages: list[str]


class SummaryOut(BaseModel):
    file_name: str
    counts: dict[str, int]
    new_suppliers: list[str]
    new_branches: list[str]
    problems: list[ProblemOut]  # the first 200
    problem_count: int


class JobOut(BaseModel):
    id: uuid.UUID
    kind: ImportKind
    status: str
    rows_done: int
    rows_total: int
    finishing: bool  # every row read: the database is finishing the work
    preview: PreviewOut
    mapping: dict[int, str] | None
    summary: SummaryOut | None
    error: str | None


class CheckIn(BaseModel):
    mapping: dict[int, str]


@router.get("/sample")
def sample_file(
    kind: ImportKind, user: User = Depends(can_import), db: Session = Depends(get_session)
) -> Response:
    if kind == "equivalents":
        raise HTTPException(404, "There is no sample file for that kind of import.")
    language = db.scalar(select(Organization.language).where(Organization.id == user.organization_id)) or "en"
    content = build_sample_file(kind, language)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={kind}-example.xlsx"},
    )


@router.get("/current")
def current(user: User = Depends(can_import), db: Session = Depends(get_session)) -> JobOut | None:
    """The shop's import in progress, or the one that just ended, to pick up where the screen left."""
    job = _current_job(db, user.organization_id)
    return _job_out(job) if job else None


@router.post("/upload")
def upload(
    file: UploadFile,
    kind: ImportKind = Form(),
    user: User = Depends(can_import),
    db: Session = Depends(get_session),
) -> JobOut:
    """Keeps the file on the server and reads the top of it: no need to send it again at each step."""
    job = _current_job(db, user.organization_id)
    if job and job.status in jobs.RUNNING:
        raise HTTPException(409, ALREADY_RUNNING)
    _forget_jobs(db, user.organization_id)

    job_id = uuid.uuid4()
    file_name = file.filename or "file"
    path = jobs.save_upload(file.file, job_id, file_name)
    try:
        table = open_table(path, file_name)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    remembered = db.scalar(
        select(ImportMapping.mapping).where(
            ImportMapping.organization_id == user.organization_id, ImportMapping.kind == kind
        )
    ) or {}
    job = ImportJob(
        id=job_id,
        organization_id=user.organization_id,
        user_id=user.id,
        kind=kind,
        file_name=file_name[:300],
        rows_total=table.row_count,
        preview=_preview(table, kind, remembered).model_dump(mode="json"),
    )
    db.add(job)
    db.commit()
    return _job_out(job)


@router.post("/{job_id}/check", status_code=202)
def check(job_id: uuid.UUID, body: CheckIn, background: BackgroundTasks, user: User = Depends(can_import), db: Session = Depends(get_session)) -> JobOut:
    job = _job_of_shop(db, job_id, user.organization_id)
    if job.status not in ("uploaded", "checked"):  # "checked": the person went back to change the columns
        raise HTTPException(409, GONE)
    check_mapping(job.kind, body.mapping, len(job.preview["columns"]))
    job.mapping = {str(column): field for column, field in body.mapping.items()}
    job.status, job.rows_done, job.finishing, job.updated_at = "checking", 0, False, utc_now()
    db.commit()
    background.add_task(jobs.run_apart, job.id, "check")
    return _job_out(job)


@router.post("/{job_id}/save", status_code=202)
def save(job_id: uuid.UUID, background: BackgroundTasks, user: User = Depends(can_import), db: Session = Depends(get_session)) -> JobOut:
    """Saves every good row in one transaction: if anything fails, nothing is saved.
    New sales remake the forecasts in the background afterwards; new stock levels save today's
    stock-outs. Both then check for alerts."""
    job = _job_of_shop(db, job_id, user.organization_id)
    if job.status != "checked":
        raise HTTPException(409, GONE)
    job.status, job.rows_done, job.finishing, job.updated_at = "saving", 0, False, utc_now()
    db.commit()
    background.add_task(_save_then_refresh, job.id, job.kind, user.organization_id)
    return _job_out(job)


@router.delete("/{job_id}", status_code=204)
def forget(job_id: uuid.UUID, user: User = Depends(can_import), db: Session = Depends(get_session)) -> None:
    """Leaves an import that isn't running: back to choosing a file."""
    job = _job_of_shop(db, job_id, user.organization_id)
    if job.status in jobs.RUNNING:
        raise HTTPException(409, ALREADY_RUNNING)
    jobs.delete_file(job)
    db.delete(job)
    db.commit()


def _save_then_refresh(job_id: uuid.UUID, kind: str, organization_id: uuid.UUID) -> None:
    jobs.run_apart(job_id, "save")
    with SessionLocal() as db:
        saved = db.scalar(select(ImportJob.status).where(ImportJob.id == job_id)) == "saved"
    if not saved:
        return
    if kind == "sales":
        run_forecasts_apart(organization_id, "sales_import")
    elif kind == "parts":  # the file may change stock (and set it to 0)
        record_stock_outs_now(organization_id)
    if kind in ("sales", "parts"):  # after the tasks above, so alerts see fresh forecasts and stock
        run_alerts_now(organization_id)


def _current_job(db: Session, organization_id: uuid.UUID) -> ImportJob | None:
    job = db.scalar(
        select(ImportJob).where(ImportJob.organization_id == organization_id).order_by(ImportJob.created_at.desc()).limit(1)
    )
    if job is None:
        return None
    jobs.mark_if_cut_off(db, job)
    age = utc_now() - job.updated_at
    if job.status in jobs.RUNNING:
        return job
    finished = job.status in ("saved", "failed")
    return job if age < (SHOW_FINISHED_FOR if finished else KEEP_UNFINISHED_FOR) else None


def _forget_jobs(db: Session, organization_id: uuid.UUID) -> None:
    for job in db.scalars(select(ImportJob).where(ImportJob.organization_id == organization_id)):
        jobs.delete_file(job)
    db.execute(delete(ImportJob).where(ImportJob.organization_id == organization_id))
    db.commit()


def _job_of_shop(db: Session, job_id: uuid.UUID, organization_id: uuid.UUID) -> ImportJob:
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.organization_id == organization_id))
    if job is None:
        raise HTTPException(404, GONE)
    return job


def _preview(table: Table, kind: ImportKind, remembered: dict[str, str]) -> PreviewOut:
    return PreviewOut(
        file_name=table.file_name,
        row_count=table.row_count,
        columns=[
            ColumnOut(index=i, header=header, samples=[show_cell(cells[i]) for cells in table.first_rows[:SAMPLE_ROWS]])
            for i, header in enumerate(table.headers)
        ],
        fields=[FieldOut(key=field.key, required=field.required) for field in FIELDS[kind]],
        mapping=_suggest_mapping(kind, table.headers, remembered),
        looks_like_sales=kind == "parts" and looks_like_sales_file(table.headers),
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


def _job_out(job: ImportJob) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        rows_done=job.rows_done,
        rows_total=job.rows_total,
        finishing=job.finishing,
        preview=job.preview,
        mapping={int(column): field for column, field in job.mapping.items()} if job.mapping else None,
        summary=SummaryOut(file_name=job.file_name, **job.summary) if job.summary else None,
        error=job.error,
    )
