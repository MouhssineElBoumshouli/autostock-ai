"""Puts a backup back (docs/INSTALL.md, "Restore"):

    docker compose -f docker-compose.prod.yml run --rm app python -m app.restore autostock-2026-10-29.dump

1. Checks the file is a good backup.
2. Backs up the current data first (backups/autostock-before-restore-<date>-<time>.dump).
3. Restores into a new database and only swaps it with the current one once that worked, so a
   failed restore changes nothing.
4. Applies this version's database changes (migrations) and prints the main tables' row counts.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import make_url

from app.backups import BackupFailed, backup_folder, is_good_backup, maintenance_lock, make_backup, run_tool, time_stamp
from app.config import DATABASE_URL
from app.db import engine

# Row count and checksum of these tables are printed after a restore and compared by the restore drill.
MAIN_TABLES = (
    "organizations", "users", "branches", "parts", "stock_levels", "sale_lines", "purchase_orders",
    "purchase_order_lines", "audit_log",
)


class RestoreFailed(Exception):
    pass


def table_fingerprints(connection: Connection) -> dict[str, tuple[int, str]]:
    """Row count and a checksum of every row's content, per main table."""
    found = {}
    for table in MAIN_TABLES:
        count, checksum = connection.execute(
            text(f"SELECT count(*), md5(coalesce(string_agg(t::text, '|' ORDER BY t.id), '')) FROM {table} t")
        ).one()
        found[table] = (count, checksum)
    return found


def restore(file: Path, folder: Path) -> dict[str, tuple[int, str]]:
    if not file.is_file() or not is_good_backup(file):
        raise RestoreFailed(f"{file.name} is not a backup AutoStock can read. Nothing was changed.")
    url = make_url(DATABASE_URL)
    name, restoring, replaced = url.database, f"{url.database}_restoring", f"{url.database}_replaced"
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with maintenance_lock(), server.connect() as admin:
            exists = admin.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name})
            if exists:
                make_backup(f"autostock-before-restore-{time_stamp()}", folder)
            admin.execute(text(f'DROP DATABASE IF EXISTS "{restoring}" WITH (FORCE)'))
            admin.execute(text(f'CREATE DATABASE "{restoring}"'))
            loaded = run_tool("pg_restore", "--no-owner", "--exit-on-error", "--dbname", restoring, str(file),
                              url=url.set(database=restoring))
            if loaded.returncode != 0:
                admin.execute(text(f'DROP DATABASE "{restoring}" WITH (FORCE)'))
                raise RestoreFailed(f"The backup could not be loaded, so nothing was changed: {loaded.stderr.strip()}")
            if exists:
                # Nobody can connect while the two are swapped; the app reconnects right after.
                admin.execute(text(f'ALTER DATABASE "{name}" WITH ALLOW_CONNECTIONS false'))
                admin.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"), {"name": name})
                admin.execute(text(f'ALTER DATABASE "{name}" RENAME TO "{replaced}"'))
            admin.execute(text(f'ALTER DATABASE "{restoring}" RENAME TO "{name}"'))
            if exists:
                admin.execute(text(f'DROP DATABASE "{replaced}" WITH (FORCE)'))
            engine.dispose()
            command.upgrade(Config("alembic.ini"), "head")
    finally:
        server.dispose()
    with engine.connect() as connection:
        return table_fingerprints(connection)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Say which backup to restore, for example: python -m app.restore autostock-2026-10-29.dump")
    folder = backup_folder()
    file = folder / Path(sys.argv[1]).name
    print(f"Restoring {file.name}. The current data is backed up first.")
    try:
        counts = restore(file, folder)
    except (RestoreFailed, BackupFailed) as failed:
        sys.exit(f"Not restored: {failed}")
    print(f"Done: {file.name} is back, with this version's database changes applied. Rows per table:")
    for table, (count, _checksum) in counts.items():
        print(f"  {table:22} {count:>9,}")


if __name__ == "__main__":
    main()
