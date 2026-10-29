"""The shop's backups, made by scripts/backup.sh (pg_dump, then read back with pg_restore).

The backup service makes one every day (docker-compose.prod.yml); the app makes one before an
update (app/start.py) and before a restore (app/restore.py). The folder (BACKUP_DIR: the shop's
backups folder) only holds checked backups: a file gets its .dump name once it has been read back.
"""

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.config import BACKUP_DIR, DATABASE_URL

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "backup.sh"
PROBLEM_FILE = "last-problem.txt"
OVERDUE_AFTER = timedelta(days=2)
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


def run_script(*args: str, folder: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, **database_env(), "BACKUP_DIR": str(folder)}
    return subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def make_backup(name: str, folder: Path) -> Path:
    """Backs up the whole database now as folder/name.dump, checked. Raises BackupFailed with the reason."""
    done = run_script("make", name, folder=folder)
    print(done.stdout, end="")
    if done.returncode != 0:
        reason = done.stderr.strip().splitlines()
        raise BackupFailed(reason[-1] if reason else "the backup could not be made.")
    return folder / f"{name}.dump"


def is_good_backup(file: Path) -> bool:
    return run_script("check", str(file), folder=file.parent).returncode == 0


def time_stamp(now: datetime | None = None) -> str:
    """For file names, in the shop's time: 2026-10-29-153012 (to the second, so two never share a name)."""
    return (now or datetime.now()).strftime("%Y-%m-%d-%H%M%S")


@dataclass
class BackupStatus:
    last_good_at: datetime | None
    kept: int
    problem: str | None  # the last backup that failed or was skipped: disk_full, database_unreachable, failed


def problem_kind(line: str) -> str:
    """The script writes a sentence (scripts/backup.sh); the website shows it in the owner's language."""
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
