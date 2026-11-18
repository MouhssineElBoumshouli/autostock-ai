"""The shop's backups, made with PostgreSQL's own tools (pg_dump, then read back with pg_restore).

The app makes one every day (keep_making_backups), one before an update (app/start.py) and one
before a restore (app/restore.py). The folder (BACKUP_DIR: the shop's backups folder) only holds
checked backups: a file gets its .dump name once it has been read back.
Plain Python, so it works the same in Docker and in the Windows app (PG_BIN: where pg_dump is).
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.config import BACKUP_DIR, DATABASE_URL, PG_BIN

log = logging.getLogger(__name__)
PROBLEM_FILE = "last-problem.txt"
OVERDUE_AFTER = timedelta(days=2)
MARGIN_BYTES = 100 * 1024 * 1024  # always leave 100 MB free on the disk
DAYS_KEPT = 14
MONTHS_KEPT = 12
KEPT_PER_KIND = 5  # backups made before an update or a restore
DAILY_NAME = re.compile(r"^autostock-(\d{4})-(\d{2})-\d{2}\.dump$")
# Taken while the database is changed as a whole (an update or a restore), so two never overlap.
MAINTENANCE_LOCK = 802_2026


class BackupFailed(Exception):
    pass


def backup_folder() -> Path:
    return Path(BACKUP_DIR)


def database_env(url: URL | None = None) -> dict[str, str]:
    """The connection settings PostgreSQL's tools read (PGHOST, PGUSER...)."""
    url = url or make_url(DATABASE_URL)
    return {"PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432), "PGUSER": url.username or "",
            "PGPASSWORD": url.password or "", "PGDATABASE": url.database or ""}


def pg_tool(name: str) -> str:
    """pg_dump, pg_restore...: from PG_BIN when set (the Windows app brings its own), else from PATH."""
    return str(Path(PG_BIN) / name) if PG_BIN else name


def run_tool(*args: str, url: URL | None = None) -> subprocess.CompletedProcess:
    hide_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no black box flashing
    return subprocess.run([pg_tool(args[0]), *args[1:]], env={**os.environ, **database_env(url)},
                          capture_output=True, text=True, creationflags=hide_window)


def record_problem(folder: Path, sentence: str) -> None:
    """Shown on the Settings page (problem_kind) until a backup works again."""
    log.warning(sentence)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / PROBLEM_FILE).write_text(f"{datetime.now():%Y-%m-%d %H:%M} {sentence}\n")


def database_size() -> int:
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            return connection.scalar(text("SELECT pg_database_size(current_database())"))
    finally:
        engine.dispose()


def free_name(folder: Path, name: str) -> Path:
    """folder/name.dump, or name-2.dump, name-3.dump... so a backup never overwrites another."""
    file, n = folder / f"{name}.dump", 1
    while file.exists():
        n += 1
        file = folder / f"{name}-{n}.dump"
    return file


def make_backup(name: str, folder: Path, margin: int = MARGIN_BYTES) -> Path:
    """Backs up the whole database now as folder/name.dump (or name-2.dump... if that name is already
    taken, so a backup never overwrites one), checked. Raises BackupFailed with the reason."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        size = database_size()
    except Exception:
        sentence = "Backup skipped: the database could not be reached."
        record_problem(folder, sentence)
        raise BackupFailed(sentence) from None
    free, needed = shutil.disk_usage(folder).free, size + margin  # a backup is smaller than the database
    if free < needed:
        sentence = f"Backup skipped: not enough free disk space ({free // 2**20} MB free, {needed // 2**20} MB needed)."
        record_problem(folder, sentence)
        raise BackupFailed(sentence)
    partial = folder / f".{name}.partial"
    if run_tool("pg_dump", "--format=custom", f"--file={partial}").returncode != 0:
        partial.unlink(missing_ok=True)
        sentence = "Backup failed: pg_dump stopped with an error."
        record_problem(folder, sentence)
        raise BackupFailed(sentence)
    if not is_good_backup(partial):
        partial.unlink(missing_ok=True)
        sentence = "Backup failed: the new file could not be read back, so it was deleted."
        record_problem(folder, sentence)
        raise BackupFailed(sentence)
    file = free_name(folder, name)
    partial.replace(file)
    (folder / PROBLEM_FILE).unlink(missing_ok=True)
    log.info("Backup saved and checked: %s (%d KB)", file, file.stat().st_size // 1024)
    return file


def is_good_backup(file: Path) -> bool:
    """Only a file pg_restore can read and that holds data counts as a backup."""
    if not file.is_file() or file.stat().st_size == 0:
        return False
    listing = run_tool("pg_restore", "--list", str(file))
    return listing.returncode == 0 and " TABLE DATA " in listing.stdout


def prune(folder: Path) -> None:
    """Keeps the 14 newest daily backups, then the newest of each older month for 12 months, and the
    5 newest made before an update and before a restore. Deletes the rest."""
    daily = sorted((f for f in folder.glob("autostock-*.dump") if DAILY_NAME.match(f.name)), key=lambda f: f.name, reverse=True)
    seen, monthly, old = set(), 0, []
    for position, file in enumerate(daily):
        month = DAILY_NAME.match(file.name).groups()
        if position < DAYS_KEPT:
            seen.add(month)
        elif month not in seen and monthly < MONTHS_KEPT:
            seen.add(month)
            monthly += 1
        else:
            old.append(file)
    for kind in ("before-update", "before-restore"):
        made = sorted(folder.glob(f"autostock-{kind}-*.dump"), key=lambda f: f.name, reverse=True)
        old += made[KEPT_PER_KIND:]
    for file in old:
        file.unlink(missing_ok=True)
        log.info("Old backup deleted: %s", file.name)
    day_ago = time.time() - 86400
    for leftover in folder.glob(".*.partial"):
        if leftover.stat().st_mtime < day_ago:
            leftover.unlink(missing_ok=True)


def has_recent_backup(folder: Path) -> bool:
    day_ago = time.time() - 86400
    return any(f.stat().st_mtime > day_ago for f in folder.glob("autostock-*.dump"))


def backup_due(folder: Path, now: datetime) -> bool:
    """At 02:00 if today's isn't made yet, and any time the last good one is older than 24 hours
    (shops switch the PC off at night)."""
    today = folder / f"autostock-{now:%Y-%m-%d}.dump"
    return not has_recent_backup(folder) or (now.hour == 2 and not today.exists())


async def keep_making_backups() -> None:
    """While the app runs (when BACKUP_DIR is set): checks every 5 minutes if a backup is due."""
    if not BACKUP_DIR:
        return
    folder = backup_folder()
    while True:
        now = datetime.now()
        if backup_due(folder, now):
            try:
                await asyncio.to_thread(make_backup, f"autostock-{now:%Y-%m-%d}", folder)
                await asyncio.to_thread(prune, folder)
            except BackupFailed:
                await asyncio.sleep(3600)  # try again in an hour, not every few minutes
            except Exception:
                log.exception("The daily backup failed")
                await asyncio.sleep(3600)
        await asyncio.sleep(300)


def time_stamp(now: datetime | None = None) -> str:
    """For file names, in the shop's time: 2026-10-29-153012 (to the second, so two never share a name)."""
    return (now or datetime.now()).strftime("%Y-%m-%d-%H%M%S")


@dataclass
class BackupStatus:
    last_good_at: datetime | None
    kept: int
    problem: str | None  # the last backup that failed or was skipped: disk_full, database_unreachable, failed


def problem_kind(line: str) -> str:
    """record_problem writes a sentence; the website shows it in the owner's language."""
    if "not enough free disk space" in line:
        return "disk_full"
    if "could not be reached" in line:
        return "database_unreachable"
    return "failed"


def backup_status(folder: Path) -> BackupStatus:
    files = list(folder.glob("autostock-*.dump"))
    last = max((file.stat().st_mtime for file in files), default=None)
    problem_file = folder / PROBLEM_FILE
    return BackupStatus(
        last_good_at=datetime.fromtimestamp(last, UTC) if last is not None else None,
        kept=len(files),
        problem=problem_kind(problem_file.read_text()) if problem_file.is_file() else None,
    )


def is_overdue(status: BackupStatus, now: datetime) -> bool:
    return status.last_good_at is None or now - status.last_good_at > OVERDUE_AFTER


@contextmanager
def maintenance_lock() -> Iterator[None]:
    """Waits until no other update or restore runs, then holds the lock. Kept in the server's own
    'postgres' database, so it lasts while the shop's database is replaced."""
    engine = create_engine(make_url(DATABASE_URL).set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MAINTENANCE_LOCK})
            try:
                yield
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MAINTENANCE_LOCK})
    finally:
        engine.dispose()


def main() -> None:
    """A backup right now:  python -m app.backups now"""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if sys.argv[1:] != ["now"]:
        sys.exit("Usage: python -m app.backups now")
    try:
        make_backup(f"autostock-now-{time_stamp()}", backup_folder())
    except BackupFailed as failed:
        sys.exit(str(failed))


if __name__ == "__main__":
    main()
