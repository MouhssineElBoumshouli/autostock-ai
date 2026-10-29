"""Starts the app on a shop's computer (docker-compose.prod.yml): updates the database safely, then serves.

- Database changes waiting (a new version was installed): a backup first,
  backups/autostock-before-update-<date>-<time>.dump. Without it, nothing is changed.
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

from app.backups import BackupFailed, backup_folder, maintenance_lock, make_backup, time_stamp
from app.db import engine

log = logging.getLogger("autostock.start")
PORT = 8000

BACKUP_FAILED = """AutoStock was not updated: the backup made before every update failed ({reason}).
Nothing was changed. Fix the reason (often a full disk), then start AutoStock again (docs/INSTALL.md, "It doesn't start")."""

UPDATE_FAILED = """AutoStock could not update its database: {error}
Nothing was lost: the database was left exactly as it was before the update.
1. Put the previous AutoStock folder back (keep .env and backups), then start it again.
2. Only if the data looks wrong afterwards, restore the copy made just before the update:
   docker compose -f docker-compose.prod.yml run --rm app python -m app.restore {backup}"""


def alembic_config() -> Config:
    return Config("alembic.ini")


def update_waiting() -> bool:
    """True when the database was made by an older version. A brand-new database has nothing to save."""
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return current is not None and current != head


def update_database() -> str | None:
    """Brings the database up to this version. Returns None, or what to tell the owner if it failed."""
    with maintenance_lock():
        backup = None
        if update_waiting():
            try:
                backup = make_backup(f"autostock-before-update-{time_stamp()}", backup_folder())
            except BackupFailed as failed:
                return BACKUP_FAILED.format(reason=failed)
        try:
            command.upgrade(alembic_config(), "head")
        except Exception as error:
            log.exception("The database update failed")
            return UPDATE_FAILED.format(error=error, backup=backup.name if backup else "<the newest autostock-....dump>")
    return None


def show_problem(message: str) -> None:
    """Instead of the app: every address answers with the problem, so the owner sees it in the browser."""
    page = f"<!doctype html><meta charset=utf-8><title>AutoStock</title><pre style='font:16px/1.5 sans-serif;white-space:pre-wrap;margin:2rem'>{html.escape(message)}</pre>"

    class ProblemPage(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(503)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

    HTTPServer(("0.0.0.0", PORT), ProblemPage).serve_forever()


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
