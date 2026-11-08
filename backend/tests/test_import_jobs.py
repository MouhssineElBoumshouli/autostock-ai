"""Big files: checked and saved in the background, followed from any page load, all or nothing."""

from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import func, select, update

from app.db import SessionLocal, utc_now
from app.imports import jobs
from app.models import ImportJob, Part, SaleLine, StockLevel
from tests.helpers import add_member, create_other_shop, logged_in_browser, member_with_own_password, set_up_shop, OWNER_PASSWORD
from tests.import_helpers import send, upload

PART_COLUMNS = {0: "sku", 1: "name"}
SALE_COLUMNS = {0: "date", 1: "sku", 2: "quantity"}
STOCK_COLUMNS = {0: "sku", 1: "name", 2: "branch", 3: "quantity"}


def parts_file(count: int = 2) -> bytes:
    return ("SKU;Name\n" + "".join(f"P-{n};Part {n}\n" for n in range(count))).encode()


def sales_file(lines: int, sku: str = "P-0") -> bytes:
    first_day = date(2026, 1, 1)
    rows = (f"{first_day + timedelta(days=n % 300):%d/%m/%Y};{sku};{n % 9 + 1}\n" for n in range(lines))
    return ("Date;SKU;Qty\n" + "".join(rows)).encode()


def count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_the_job_is_found_again_after_a_page_reload(browser):
    set_up_shop(browser)
    uploaded = upload(browser, "parts", "parts.csv", parts_file()).json()

    assert browser.get("/api/imports/current").json()["id"] == uploaded["id"]
    assert uploaded["status"] == "uploaded"
    assert uploaded["rows_total"] == 2

    browser.post(f"/api/imports/{uploaded['id']}/check", json={"mapping": PART_COLUMNS})
    reloaded = browser.get("/api/imports/current").json()
    assert reloaded["status"] == "checked"
    assert reloaded["summary"]["counts"]["new_parts"] == 2
    assert reloaded["mapping"] == {"0": "sku", "1": "name"}
    assert count(Part) == 0

    browser.post(f"/api/imports/{uploaded['id']}/save")
    assert browser.get("/api/imports/current").json()["status"] == "saved"
    assert count(Part) == 2


def test_the_real_background_process_saves_and_reports_rows(browser, monkeypatch):
    monkeypatch.undo()  # the real separate process, not the shortcut every other test takes
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())

    answer = send(browser, "save", "sales", "sales.csv", SALE_COLUMNS, content=sales_file(25_000))

    assert answer.json()["counts"] == {"new_sales": 25_000, "already_imported": 0, "problem_rows": 0}
    job = browser.get("/api/imports/current").json()
    assert (job["rows_done"], job["rows_total"]) == (25_000, 25_000)
    assert count(SaleLine) == 25_000


def test_progress_is_written_while_reading(browser, monkeypatch):
    seen = []
    report = jobs._report_rows
    monkeypatch.setattr(jobs, "_report_rows", lambda job_id, rows: (seen.append(rows), report(job_id, rows)))
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())

    send(browser, "check", "sales", "sales.csv", SALE_COLUMNS, content=sales_file(25_000))

    assert seen == [10_000, 20_000]


def test_duplicates_in_a_big_file_are_counted_one_by_one(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())
    three_same = b"Date;SKU;Qty\n" + b"05/01/2026;P-0;2\n" * 3
    two_same = b"Date;SKU;Qty\n" + b"05/01/2026;P-0;2\n" * 2

    send(browser, "save", "sales", "two.csv", SALE_COLUMNS, content=two_same)
    answer = send(browser, "save", "sales", "three.csv", SALE_COLUMNS, content=three_same)

    assert answer.json()["counts"] == {"new_sales": 1, "already_imported": 2, "problem_rows": 0}
    assert count(SaleLine) == 3


def test_importing_the_same_history_again_adds_nothing(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())
    history = sales_file(3000)

    send(browser, "save", "sales", "sales.csv", SALE_COLUMNS, content=history)
    answer = send(browser, "save", "sales", "sales.csv", SALE_COLUMNS, content=history)

    assert answer.json()["counts"] == {"new_sales": 0, "already_imported": 3000, "problem_rows": 0}
    assert count(SaleLine) == 3000


def test_every_problem_row_is_counted_but_only_the_first_are_listed(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())

    answer = send(browser, "check", "sales", "sales.csv", SALE_COLUMNS, content=sales_file(1000, sku="UNKNOWN"))

    summary = answer.json()
    assert summary["problem_count"] == summary["counts"]["problem_rows"] == 1000
    assert len(summary["problems"]) == 200
    assert summary["problems"][0]["row"] == 2


def test_a_part_can_come_on_one_row_per_branch(browser):
    set_up_shop(browser)
    content = "SKU;Name;Branch;Qty\nA-1;Filter;Rabat;4\nA-1;Filter;Agadir;6\nA-2;Pump;Rabat;1\n".encode()

    answer = send(browser, "save", "parts", "parts.csv", STOCK_COLUMNS, content=content)

    assert answer.json()["counts"]["new_parts"] == 2
    assert answer.json()["counts"]["problem_rows"] == 0
    assert answer.json()["new_branches"] == ["Agadir", "Rabat"]
    assert count(Part) == 2
    assert count(StockLevel) == 3


def test_the_same_part_twice_for_one_branch_is_a_problem(browser):
    set_up_shop(browser)
    content = "SKU;Name;Branch;Qty\nA-1;Filter;Rabat;4\nA-1;Filter;rabat;6\nA-2;Pump;Rabat;1\n".encode()

    answer = send(browser, "check", "parts", "parts.csv", STOCK_COLUMNS, content=content)

    assert answer.json()["counts"]["problem_rows"] == 2
    assert answer.json()["problems"][0]["messages"] == ["Same SKU twice in the file (rows 2, 3)"]


def test_a_part_with_two_different_names_is_a_problem(browser):
    set_up_shop(browser)
    content = "SKU;Name;Branch;Qty\nA-1;Filter;Rabat;4\nA-1;Pump;Agadir;6\n".encode()

    answer = send(browser, "check", "parts", "parts.csv", STOCK_COLUMNS, content=content)

    assert answer.json()["counts"] == {"new_parts": 0, "updated_parts": 0, "unchanged_parts": 0, "delivery_times": 0, "delivery_only": 0,
                                       "unread_delivery_times": 0, "problem_rows": 2}
    assert answer.json()["problems"][1]["messages"] == ["Same SKU with different details (rows 2, 3)"]
    assert answer.json()["new_branches"] == []


def test_negative_stock_comes_in_as_it_is(browser):
    set_up_shop(browser)
    content = "SKU;Name;Branch;Qty\nA-1;Filter;Rabat;-3\n".encode()

    answer = send(browser, "save", "parts", "parts.csv", STOCK_COLUMNS, content=content)

    assert answer.json()["counts"]["problem_rows"] == 0
    with SessionLocal() as db:
        assert db.scalar(select(StockLevel.quantity)) == -3


def test_a_workbook_can_carry_its_rows_on_several_sheets(browser):
    set_up_shop(browser)
    send(browser, "save", "parts", "parts.csv", PART_COLUMNS, content=parts_file())
    workbook = Workbook()
    first = workbook.active
    first.title = "Ventes 1"
    second = workbook.create_sheet("Ventes 2")
    other = workbook.create_sheet("Notes")
    for sheet in (first, second):
        sheet.append(["Date", "SKU", "Qty"])
    first.append([date(2026, 1, 5), "P-0", 1])
    second.append([date(2026, 1, 6), "P-1", 2])
    second.append([date(2026, 1, 7), "NOPE", 3])
    other.append(["Nothing here", "to read"])
    other.append(["a", "b"])
    buffer = BytesIO()
    workbook.save(buffer)

    answer = send(browser, "save", "sales", "sales.xlsx", SALE_COLUMNS, content=buffer.getvalue())

    assert answer.json()["counts"] == {"new_sales": 2, "already_imported": 0, "problem_rows": 1}
    [problem] = answer.json()["problems"]
    assert (problem["sheet"], problem["row"]) == ("Ventes 2", 3)
    assert count(SaleLine) == 2


def test_a_second_upload_replaces_an_idle_one_but_waits_for_a_running_one(browser):
    set_up_shop(browser)
    first = upload(browser, "parts", "parts.csv", parts_file()).json()
    second = upload(browser, "parts", "parts.csv", parts_file()).json()
    assert browser.get("/api/imports/current").json()["id"] == second["id"]
    assert not jobs.uploaded_file(first["id"], "parts.csv").exists()

    with SessionLocal() as db:
        db.execute(update(ImportJob).values(status="saving", updated_at=utc_now()))
        db.commit()

    refused = upload(browser, "parts", "parts.csv", parts_file())
    assert refused.status_code == 409
    assert browser.delete(f"/api/imports/{second['id']}").status_code == 409


def test_a_job_cut_off_by_a_restart_says_so_and_saved_nothing(browser):
    set_up_shop(browser)
    job = upload(browser, "parts", "parts.csv", parts_file()).json()
    with SessionLocal() as db:
        long_ago = utc_now() - jobs.CUT_OFF_AFTER - timedelta(seconds=1)
        db.execute(update(ImportJob).values(status="saving", updated_at=long_ago))
        db.commit()

    found = browser.get("/api/imports/current").json()

    assert found["id"] == job["id"]
    assert found["status"] == "failed"
    assert found["error"] == jobs.NOTHING_SAVED
    assert count(Part) == 0


def test_leaving_an_import_removes_its_file(browser):
    set_up_shop(browser)
    job = upload(browser, "parts", "parts.csv", parts_file()).json()

    assert browser.delete(f"/api/imports/{job['id']}").status_code == 204

    assert browser.get("/api/imports/current").json() is None
    assert not jobs.uploaded_file(job["id"], "parts.csv").exists()


def test_a_broken_file_found_while_checking_fails_with_a_plain_message(browser, monkeypatch):
    set_up_shop(browser)
    job = upload(browser, "parts", "parts.csv", parts_file(30)).json()
    monkeypatch.setattr("app.imports.reading.MAX_ROWS", 20)

    browser.post(f"/api/imports/{job['id']}/check", json={"mapping": PART_COLUMNS})

    found = browser.get("/api/imports/current").json()
    assert found["status"] == "failed"
    assert found["error"] == "This file has more than 20 rows. Split it into smaller files."


def test_staff_and_other_shops_cannot_touch_a_job(browser):
    set_up_shop(browser)
    job = upload(browser, "parts", "parts.csv", parts_file()).json()
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    other = logged_in_browser(create_other_shop().email, OWNER_PASSWORD)

    assert staff.get("/api/imports/current").status_code == 403
    assert other.get("/api/imports/current").json() is None
    assert other.post(f"/api/imports/{job['id']}/check", json={"mapping": PART_COLUMNS}).status_code == 404
    assert other.post(f"/api/imports/{job['id']}/save").status_code == 404
    assert other.delete(f"/api/imports/{job['id']}").status_code == 404
