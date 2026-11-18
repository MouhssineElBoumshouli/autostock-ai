"""Starts the app on a shop's computer (docker-compose.prod.yml): updates the database safely, then serves.

- Database changes waiting (a new version was installed): a backup first,
  backups/autostock-before-update-<date>-<time>.dump. Without it, nothing is changed.
- A newer AutoStock already updated the database: this older one doesn't start and says what to do.
- A change fails: the database stays exactly as it was (all changes run in one transaction), the
  app does not start, and every page (and the log) says which backup to restore if needed.
"""

import html
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError

from app.backups import BackupFailed, backup_folder, maintenance_lock, make_backup, time_stamp
from app.db import engine

log = logging.getLogger("autostock.start")
PORT = 8000
# How the owner restores a backup: Docker here, the Windows app sets its own (app/desktop.py).
RESTORE_COMMAND = os.environ.get("RESTORE_COMMAND", "docker compose -f docker-compose.prod.yml run --rm app python -m app.restore")

BACKUP_FAILED = """AutoStock was not updated: the backup made before every update failed ({reason}).
Nothing was changed. Fix the reason (often a full disk), then start AutoStock again."""

NEWER_DATABASE = """This database was updated by a newer AutoStock, so this version can't use it.
Use the newer version, or restore the backup made before the update (autostock-before-update-....dump):
   {restore} autostock-before-update-....dump
Anything entered since the update is then lost."""

UPDATE_FAILED = """AutoStock could not update its database: {error}
Nothing was lost: the database was left exactly as it was before the update.
1. Put the previous AutoStock folder back (keep .env and backups), then start it again.
2. Only if the data looks wrong afterwards, restore the copy made just before the update:
   {restore} {backup}"""


def alembic_config() -> Config:
    return Config("alembic.ini")


def database_version() -> str:
    """How the database compares with this version: "new" (empty, nothing to save yet), "same",
    "older" (an update is waiting) or "newer" (a newer AutoStock already updated it)."""
    scripts = ScriptDirectory.from_config(alembic_config())
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if current is None:
        return "new"
    if current == scripts.get_current_head():
        return "same"
    try:
        scripts.get_revision(current)
    except CommandError:  # a revision this version has never heard of
        return "newer"
    return "older"


def update_database() -> str | None:
    """Brings the database up to this version. Returns None, or what to tell the owner if it failed."""
    with maintenance_lock():
        version = database_version()
        if version == "newer":
            return NEWER_DATABASE.format(restore=RESTORE_COMMAND)
        backup = None
        if version == "older":
            try:
                backup = make_backup(f"autostock-before-update-{time_stamp()}", backup_folder())
            except BackupFailed as failed:
                return BACKUP_FAILED.format(reason=failed)
        try:
            command.upgrade(alembic_config(), "head")
        except Exception as error:
            log.exception("The database update failed")
            return UPDATE_FAILED.format(restore=RESTORE_COMMAND, error=error, backup=backup.name if backup else "<the newest autostock-....dump>")
    return None


def show_problem(message: str, port: int = PORT) -> None:
    """Instead of the app: every address answers with the problem, so the owner sees it in the browser."""
    page = f"<!doctype html><meta charset=utf-8><title>AutoStock</title><pre style='font:16px/1.5 sans-serif;white-space:pre-wrap;margin:2rem'>{html.escape(message)}</pre>"

    class ProblemPage(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(503)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

    HTTPServer(("0.0.0.0", port), ProblemPage).serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    problem = update_database()
    if problem:
        print(problem, flush=True)
        show_problem(problem)
        return
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORT), "--no-server-header"])


if __name__ == "__main__":
    main()
