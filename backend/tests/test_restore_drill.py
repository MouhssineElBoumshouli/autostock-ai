"""The restore drill: back up a shop, lose the database, restore it; every main table must come
back identical (row counts and a checksum of every row). Then the update and password tools."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from app import start
from app.backups import make_backup
from app.config import DATABASE_URL
from app.db import SessionLocal, engine
from app.models import AuditLog, User, UserSession
from app.reset_password import ResetRefused, reset_password
from app.restore import RestoreFailed, restore, table_fingerprints
from tests.backup_helpers import shop_with_everything
from tests.helpers import OWNER_PASSWORD, logged_in_browser, new_browser, set_up_shop


def fingerprints() -> dict:
    with engine.connect() as connection:
        return table_fingerprints(connection)


def drop_the_database() -> None:
    engine.dispose()
    url = make_url(DATABASE_URL)
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as admin:
        admin.execute(text(f'DROP DATABASE "{url.database}" WITH (FORCE)'))
    server.dispose()


def test_drill_back_up_lose_the_database_restore_identical(browser, tmp_path):
    shop_with_everything(browser)
    before = fingerprints()
    assert all(count > 0 for count, _checksum in before.values()), before
    backup = make_backup("autostock-2026-10-29", tmp_path)

    drop_the_database()
    after = restore(backup, tmp_path)

    assert after == before
    assert logged_in_browser("owner@shop.ma", OWNER_PASSWORD).get("/api/today").status_code == 200


def test_restoring_backs_up_the_current_data_first(browser, tmp_path):
    set_up_shop(browser)
    backup = make_backup("autostock-2026-10-28", tmp_path)
    added = browser.post("/api/users", json={"name": "Late", "email": "late@shop.ma", "role": "staff", "temporary_password": "temporary-pass-1"})
    assert added.status_code == 201
    with_late_user = fingerprints()

    restore(backup, tmp_path)

    [safety] = tmp_path.glob("autostock-before-restore-*.dump")
    assert fingerprints()["users"][0] == with_late_user["users"][0] - 1
    assert restore(safety, tmp_path) == with_late_user  # the data from just before the restore is safe


def test_a_bad_file_is_refused_and_nothing_changes(browser, tmp_path):
    set_up_shop(browser)
    before = fingerprints()
    (tmp_path / "autostock-2026-10-29.dump").write_text("not a backup")

    with pytest.raises(RestoreFailed):
        restore(tmp_path / "autostock-2026-10-29.dump", tmp_path)

    assert fingerprints() == before
    assert list(tmp_path.glob("autostock-before-restore-*")) == []


def test_an_update_backs_up_first_then_changes_the_database(browser, tmp_path, monkeypatch):
    set_up_shop(browser)
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))
    command.downgrade(Config("alembic.ini"), "-1")  # as if the shop still ran the previous version
    assert start.database_version() == "older"

    assert start.update_database() is None

    [backup] = tmp_path.glob("autostock-before-update-*.dump")
    assert start.database_version() == "same"
    assert start.update_database() is None  # nothing waiting: no new backup
    assert list(tmp_path.glob("autostock-before-update-*.dump")) == [backup]


def test_a_failed_update_leaves_the_database_as_it_was_and_names_the_backup(browser, tmp_path, monkeypatch):
    set_up_shop(browser)
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))
    command.downgrade(Config("alembic.ini"), "-1")

    def failing_upgrade(*_args) -> None:
        raise RuntimeError("disk error")

    monkeypatch.setattr(start.command, "upgrade", failing_upgrade)
    problem = start.update_database()
    monkeypatch.undo()

    [backup] = tmp_path.glob("autostock-before-update-*.dump")
    assert "could not update its database: disk error" in problem and backup.name in problem
    assert start.database_version() == "older"  # still the previous version, untouched
    command.upgrade(Config("alembic.ini"), "head")


def test_an_older_version_refuses_a_database_a_newer_one_updated(browser, tmp_path, monkeypatch):
    set_up_shop(browser)
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '0099'"))  # made by a future version
    try:
        assert start.database_version() == "newer"
        problem = start.update_database()
        assert problem == start.NEWER_DATABASE and "autostock-before-update-" in problem
        assert list(tmp_path.iterdir()) == []  # nothing backed up, nothing changed
    finally:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0015'"))


def test_a_new_database_needs_no_backup_before_its_first_start(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "database_version", lambda: "new")
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))

    assert start.update_database() is None
    assert list(tmp_path.iterdir()) == []


def test_reset_password_from_the_shop_computer(browser):
    set_up_shop(browser)
    other_device = logged_in_browser("owner@shop.ma", OWNER_PASSWORD)

    with SessionLocal() as db:
        with pytest.raises(ResetRefused, match="at least 10 characters"):
            reset_password(db, "owner@shop.ma", "short")
        with pytest.raises(ResetRefused, match="Nobody has the email"):
            reset_password(db, "nobody@shop.ma", "a-new-password-1")
        reset_password(db, " Owner@Shop.ma ", "a-new-password-1")

    assert other_device.get("/api/auth/me").status_code == 401  # logged out everywhere
    old = new_browser().post("/api/auth/login", json={"email": "owner@shop.ma", "password": OWNER_PASSWORD})
    assert old.status_code == 401
    assert logged_in_browser("owner@shop.ma", "a-new-password-1").get("/api/today").status_code == 200
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@shop.ma"))
        logged = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "user.password_set_on_shop_computer", AuditLog.user_id == owner.id
        )
        assert db.scalar(logged) == 1
        assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == owner.id)) == 1
