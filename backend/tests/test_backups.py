"""Daily backups (scripts/backup.sh): checked before they count, old ones pruned, a full disk skipped;
what the owner sees in Settings and on Today."""

import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.backups import backup_status, is_good_backup, is_overdue, make_backup
from tests.backup_helpers import run_backup_script, shop_with_everything
from tests.helpers import add_member, member_with_own_password, set_up_shop

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_a_backup_is_checked_before_it_counts(browser, tmp_path):
    set_up_shop(browser)

    file = make_backup("autostock-2026-10-29", tmp_path)

    assert file == tmp_path / "autostock-2026-10-29.dump" and is_good_backup(file)
    assert [path.name for path in tmp_path.iterdir()] == ["autostock-2026-10-29.dump"]  # no leftovers
    status = backup_status(tmp_path)
    assert status.kept == 1 and status.problem is None and not is_overdue(status, datetime.now(UTC))


def test_an_empty_or_broken_file_is_not_a_backup(tmp_path):
    (tmp_path / "empty.dump").write_bytes(b"")
    (tmp_path / "broken.dump").write_bytes(b"not a backup")

    assert not is_good_backup(tmp_path / "empty.dump")
    assert not is_good_backup(tmp_path / "broken.dump")


def test_not_enough_disk_space_skips_the_backup_and_says_so(browser, tmp_path):
    set_up_shop(browser)

    done = run_backup_script("make", "autostock-2026-10-29", folder=tmp_path, BACKUP_MARGIN_KB=str(10**12))

    assert done.returncode == 1
    assert "Backup skipped: not enough free disk space" in done.stderr
    assert not (tmp_path / "autostock-2026-10-29.dump").exists()
    assert backup_status(tmp_path).problem == "disk_full"


def test_old_backups_are_pruned_to_14_days_and_one_per_month_for_12_months(tmp_path):
    first = datetime(2025, 1, 1)
    days = [first + timedelta(days=n) for n in range(700)]  # Jan 2025 to Nov 2026, every day
    for day in days:
        (tmp_path / f"autostock-{day:%Y-%m-%d}.dump").write_text("x")
    for n in range(8):
        (tmp_path / f"autostock-before-update-2026-10-0{n + 1}-120000.dump").write_text("x")

    assert run_backup_script("prune", folder=tmp_path).returncode == 0

    kept = sorted(path.name for path in tmp_path.iterdir())
    daily = [name for name in kept if "before" not in name]
    newest = [f"autostock-{day:%Y-%m-%d}.dump" for day in days[-14:]]
    assert daily[-14:] == newest
    monthly = daily[:-14]
    assert len(monthly) == 12
    assert len({name[10:17] for name in monthly}) == 12  # one per month
    assert all(name[18:20] in ("28", "29", "30", "31") for name in monthly)  # the month's last day
    assert len([name for name in kept if "before-update" in name]) == 5


def test_status_shows_the_newest_backup_and_two_days_without_one_is_overdue(tmp_path):
    old = tmp_path / "autostock-2026-10-20.dump"
    old.write_text("x")
    three_days_ago = time.time() - 3 * 86400
    os.utime(old, (three_days_ago, three_days_ago))

    status = backup_status(tmp_path)

    assert status.kept == 1
    assert is_overdue(status, datetime.now(UTC))
    assert is_overdue(backup_status(tmp_path / "missing"), datetime.now(UTC))  # none at all


def test_the_owner_sees_backups_in_settings_and_staff_do_not(browser, tmp_path, monkeypatch):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    assert browser.get("/api/backups").json() == {"on": False, "last_good_at": None, "kept": 0, "problem": None}

    monkeypatch.setattr("app.api.backups.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))
    make_backup("autostock-2026-10-29", tmp_path)
    shown = browser.get("/api/backups").json()

    assert shown["on"] and shown["kept"] == 1 and shown["last_good_at"] is not None
    assert staff.get("/api/backups").status_code == 403


def test_only_the_owner_gets_a_needs_action_warning_when_backups_stopped(browser, tmp_path, monkeypatch):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    monkeypatch.setattr("app.api.today.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backups.BACKUP_DIR", str(tmp_path))

    assert browser.get("/api/today").json()["backup_overdue"] == {"last_good_at": None}
    assert staff.get("/api/today").json()["backup_overdue"] is None

    make_backup("autostock-2026-10-29", tmp_path)
    assert browser.get("/api/today").json()["backup_overdue"] is None


def test_a_backup_holds_the_whole_shop(browser, tmp_path):
    shop_with_everything(browser)

    listing = subprocess.run(["pg_restore", "--list", str(make_backup("all", tmp_path))], capture_output=True, text=True).stdout

    for table in ("parts", "sale_lines", "purchase_orders", "users", "audit_log", "alembic_version"):
        assert f"TABLE DATA public {table} " in listing


def check_password(password: str | None) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key != "POSTGRES_PASSWORD"}
    if password is not None:
        env["POSTGRES_PASSWORD"] = password
    return subprocess.run(["sh", str(SCRIPTS / "check-password.sh")], env=env, capture_output=True, text=True)


def test_a_weak_database_password_is_refused_with_a_plain_message():
    for weak in (None, "", "change-me", "autostock", "only15characters"[:15]):
        refused = check_password(weak)
        assert refused.returncode == 1, weak
        assert "POSTGRES_PASSWORD in the .env file is missing or too weak" in refused.stderr
    assert check_password("a-strong-password-16").returncode == 0
