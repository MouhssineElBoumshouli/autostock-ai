"""Checks and saves one uploaded file in the background, in its own lower-priority process, so a
file of millions of lines never slows the pages. The saved rows stay all or nothing: one
transaction. Progress goes through a second connection, so the screen sees it while that runs.
"""

import logging
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.audit import record_change
from app.db import SessionLocal, utc_now
from app.imports.equivalents_import import plan_equivalents, save_equivalents
from app.imports.fields import ImportKind, check_mapping
from app.imports.parts_import import analyze_parts, plan_parts, save_parts
from app.imports.plan import Summary
from app.imports.reading import Table, open_table, saved_file_suffix
from app.imports.sales_import import analyze_sales, plan_sales, save_sales
from app.imports.values import normalize_header
from app.models import ImportJob, ImportMapping, User

log = logging.getLogger(__name__)
APP_FOLDER = Path(__file__).resolve().parents[2]  # where `python -m app...` works
UPLOADS = Path(tempfile.gettempdir()) / "autostock-imports"
LOWER_PRIORITY = 10
RUNNING = ("checking", "saving")
HEARTBEAT_SECONDS = 15
CUT_OFF_AFTER = timedelta(seconds=90)  # no heartbeat for this long: the process is gone
NOTHING_SAVED = "The import stopped before it finished. Nothing was saved. Start again."


def uploaded_file(job_id: uuid.UUID, file_name: str) -> Path:
    return UPLOADS / f"{job_id}{saved_file_suffix(file_name)}"


def delete_file(job: ImportJob) -> None:
    uploaded_file(job.id, job.file_name).unlink(missing_ok=True)


def save_upload(source, job_id: uuid.UUID, file_name: str) -> Path:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = uploaded_file(job_id, file_name)
    with open(path, "wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    return path


def run_apart(job_id: uuid.UUID, step: str) -> None:
    """What the website starts: the step in its own process, so all its memory is given back when
    it ends. Waits for it to finish."""
    finished = subprocess.run([sys.executable, "-m", "app.imports.jobs", str(job_id), step], cwd=APP_FOLDER)
    if finished.returncode != 0:  # stopped from outside (out of memory, ...): it could not record that itself
        log.error("Import %s stopped with code %s", job_id, finished.returncode)
        _record_failure(job_id, NOTHING_SAVED)


def mark_if_cut_off(db: Session, job: ImportJob) -> None:
    """A running job that stopped moving was cut off (power cut, restart). Its transaction went with
    it, so nothing was saved: the screen says so instead of waiting forever."""
    if job.status in RUNNING and utc_now() - job.updated_at > CUT_OFF_AFTER:
        job.status = "failed"
        job.error = NOTHING_SAVED
        delete_file(job)
        db.commit()


def run_step(job_id: uuid.UUID, step: str) -> None:
    finished_status = {"check": "checked", "save": "saved"}[step]
    started = perf_counter()
    with SessionLocal() as db:
        job = db.get(ImportJob, job_id)
        path = uploaded_file(job.id, job.file_name)
    alive = threading.Event()
    threading.Thread(target=_heartbeat, args=(job_id, alive), daemon=True).start()
    try:
        table = open_table(path, job.file_name)
        table.on_progress = lambda rows: _report_rows(job_id, rows)
        with SessionLocal() as db:
            summary = _go_through_file(db, job, table, finished_status == "saved")
        _finish(job_id, finished_status, summary, table.rows_read)
        if finished_status == "saved":
            path.unlink(missing_ok=True)
        memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        log.info("Import %s %s: %s rows in %.1f s, %.0f MB at most", job.file_name, finished_status, table.rows_read, perf_counter() - started, memory_mb)
    except HTTPException as refused:  # what the reader tells the person about the file
        path.unlink(missing_ok=True)
        _record_failure(job_id, refused.detail)
    except Exception:
        log.exception("Import failed for %s", job_id)
        path.unlink(missing_ok=True)
        _record_failure(job_id, NOTHING_SAVED)
    finally:
        alive.set()


def _go_through_file(db: Session, job: ImportJob, table: Table, keep: bool) -> dict[str, Any]:
    """The check and the save are the same pass, so what the Check step shows is what is saved
    (the file is read again in case the shop's data changed in between). Only the save stays."""
    mapping = {int(column): field for column, field in job.mapping.items()}
    columns = check_mapping(job.kind, mapping, len(table.headers))
    user = db.get(User, job.user_id)
    # One import at a time per shop, so two people can't import the same parts at once.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:shop, 0))"), {"shop": str(job.organization_id)})
    plan = _plan(db, job.kind, job.organization_id, table, columns)
    _report_finishing(job.id)
    if not keep:
        db.rollback()  # the temporary tables go with it
        return summary_json(plan.summary)
    _save(db, job, user, plan)
    _remember_mapping(db, job, table, mapping)
    record_change(
        db, user, "import.saved", "import", uuid.uuid4(),
        after={
            "kind": job.kind,
            "file_name": job.file_name,
            **plan.summary.counts,
            "new_suppliers": len(plan.summary.new_suppliers),
            "new_branches": len(plan.summary.new_branches),
        },
    )
    db.commit()
    _analyze(db, job.kind)
    return summary_json(plan.summary)


def _plan(db: Session, kind: ImportKind, organization_id: uuid.UUID, table: Table, columns: dict[str, int]):
    if kind == "parts":
        return plan_parts(db, organization_id, table, columns)
    if kind == "sales":
        return plan_sales(db, organization_id, table, columns)
    return plan_equivalents(db, organization_id, table, columns)


def _save(db: Session, job: ImportJob, user: User, plan) -> None:
    if job.kind == "parts":
        save_parts(db, job.organization_id, plan)
    elif job.kind == "sales":
        save_sales(db, job.organization_id, plan)
    else:
        save_equivalents(db, job.organization_id, user.id, plan)


def _analyze(db: Session, kind: str) -> None:
    if kind == "parts":
        analyze_parts(db)
    elif kind == "sales":
        analyze_sales(db)
    db.commit()


def _remember_mapping(db: Session, job: ImportJob, table: Table, by_column: dict[int, str]) -> None:
    """Adds this import's column matching to what is remembered, without losing headers from past imports
    that aren't in this file (e.g. a supplier's file has different columns than the shop's own export).
    """
    this_import = {normalize_header(table.headers[column]): field for column, field in by_column.items()}
    row = db.scalar(
        select(ImportMapping).where(ImportMapping.organization_id == job.organization_id, ImportMapping.kind == job.kind)
    )
    if row is None:
        db.add(ImportMapping(organization_id=job.organization_id, kind=job.kind, mapping=this_import))
    else:
        row.mapping = {**row.mapping, **this_import}


def summary_json(summary: Summary) -> dict[str, Any]:
    return {
        "counts": summary.counts,
        "new_suppliers": summary.new_suppliers,
        "new_branches": summary.new_branches,
        "problems": [{"row": p.row, "sheet": p.sheet, "messages": p.messages} for p in summary.problems],
        "problem_count": summary.problem_count,
    }


def _report_rows(job_id: uuid.UUID, rows: int) -> None:
    with SessionLocal() as db:
        db.execute(update(ImportJob).where(ImportJob.id == job_id).values(rows_done=rows, updated_at=utc_now()))
        db.commit()


def _report_finishing(job_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        db.execute(update(ImportJob).where(ImportJob.id == job_id).values(finishing=True, updated_at=utc_now()))
        db.commit()


def _heartbeat(job_id: uuid.UUID, stop: threading.Event) -> None:
    """Says "still working", also during the long minutes when only PostgreSQL has work to do."""
    while not stop.wait(HEARTBEAT_SECONDS):
        with SessionLocal() as db:
            db.execute(update(ImportJob).where(ImportJob.id == job_id).values(updated_at=utc_now()))
            db.commit()


def _finish(job_id: uuid.UUID, status: str, summary: dict[str, Any], rows: int) -> None:
    with SessionLocal() as db:
        db.execute(
            update(ImportJob)
            .where(ImportJob.id == job_id)
            .values(status=status, summary=summary, rows_done=rows, rows_total=rows, finishing=False, updated_at=utc_now())
        )
        db.commit()


def _record_failure(job_id: uuid.UUID, message: str) -> None:
    with SessionLocal() as db:
        db.execute(
            update(ImportJob)
            .where(ImportJob.id == job_id, ImportJob.status.in_(RUNNING))
            .values(status="failed", error=message, finishing=False, updated_at=utc_now())
        )
        db.commit()


if __name__ == "__main__":  # started by run_apart
    logging.basicConfig(level=logging.INFO)
    os.nice(LOWER_PRIORITY)
    run_step(uuid.UUID(sys.argv[1]), sys.argv[2])
