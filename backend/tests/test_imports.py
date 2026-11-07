from sqlalchemy import func, select

from app.db import SessionLocal
from app.imports.jobs import NOTHING_SAVED
from app.models import Branch, Part, SaleLine, StockLevel, Supplier
from tests.helpers import add_member, audit_rows, create_other_shop, logged_in_browser, member_with_own_password, set_up_shop, OWNER_PASSWORD
from tests.import_helpers import PARTS_MAPPING, SALES_MAPPING, import_parts, import_sales, send


def count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


# Step 1 and 2: upload and column preview


def test_preview_shows_columns_with_first_5_rows(browser):
    set_up_shop(browser)

    preview = send(browser, "preview", "parts", "parts_fr_messy.xlsx").json()

    assert preview["row_count"] == 29
    headers = [column["header"] for column in preview["columns"]]
    assert headers == [
        "Réf.", "Désignation", "Marque", "Famille", "Réf OEM", "Prix d'achat (DH)", "Prix de vente",
        "Stock mini", "Qté en stock", "Dépôt", "Fournisseur",
    ]
    assert preview["columns"][0]["samples"] == ["bp-001", "BP-002", "DS-110", "FL-200", "FL-205"]
    assert {"key": "sku", "required": True} in preview["fields"]
    assert {"key": "brand", "required": False} in preview["fields"]
    # Nobody has imported into this shop yet, so this comes from the free local column guesser,
    # not from memory.
    assert {int(k): v for k, v in preview["mapping"].items()} == PARTS_MAPPING


def test_preview_reads_french_csv_with_semicolons_and_windows_encoding(browser):
    set_up_shop(browser)

    preview = send(browser, "preview", "sales", "sales_fr_messy.csv").json()

    assert [c["header"] for c in preview["columns"]] == ["Date de vente", "Réf. article", "Qté", "Prix unitaire (DH)", "Dépôt"]
    assert preview["row_count"] == 20  # the empty row is left out


def test_column_matching_is_remembered_for_next_time(browser):
    set_up_shop(browser)
    import_parts(browser)

    preview = send(browser, "preview", "parts", "parts_fr_messy.xlsx").json()

    assert {int(k): v for k, v in preview["mapping"].items()} == PARTS_MAPPING
    # A different kind of file: nothing remembered yet, but the column guesser still gets it right.
    sales_preview = send(browser, "preview", "sales", "sales_fr_messy.csv").json()
    assert {int(k): v for k, v in sales_preview["mapping"].items()} == SALES_MAPPING


# Step 3: check (nothing is saved)


def test_check_counts_and_lists_every_problem_without_saving(browser):
    set_up_shop(browser)

    summary = send(browser, "check", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING).json()

    assert summary["counts"] == {"new_parts": 22, "updated_parts": 0, "unchanged_parts": 0, "delivery_times": 0, "delivery_only": 0, "unread_delivery_times": 0, "problem_rows": 7}
    assert summary["new_branches"] == ["Casablanca", "Rabat"]
    assert len(summary["new_suppliers"]) == 11
    assert {p["row"]: p["messages"] for p in summary["problems"]} == {
        28: ["SKU is missing"],
        29: ["Quantity is not a number"],
        30: ["Quantity must be a whole number"],
        31: ["Same SKU with different details (rows 31, 32)"],
        32: ["Same SKU with different details (rows 31, 32)"],
        33: ["Sale price can't be negative"],
        34: ["Name is missing (needed for a new part)"],
    }
    assert count(Part) == 0
    assert count(Supplier) == 0


def test_check_shows_updates_of_existing_parts(browser):
    set_up_shop(browser)
    import_parts(browser)

    summary = send(browser, "check", "parts", "parts_en_clean.csv", PARTS_MAPPING).json()

    assert summary["counts"] == {"new_parts": 12, "updated_parts": 3, "unchanged_parts": 0, "delivery_times": 0, "delivery_only": 0, "unread_delivery_times": 0, "problem_rows": 0}
    assert summary["new_branches"] == ["Main"]


def test_importing_the_same_parts_again_changes_nothing(browser):
    set_up_shop(browser)
    import_parts(browser)

    summary = send(browser, "check", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING).json()

    assert summary["counts"]["new_parts"] == 0
    assert summary["counts"]["updated_parts"] == 0
    assert summary["counts"]["unchanged_parts"] == 22


def test_sales_problems(browser):
    set_up_shop(browser)
    import_parts(browser)

    summary = send(browser, "check", "sales", "sales_fr_messy.csv", SALES_MAPPING).json()

    assert summary["counts"] == {"new_sales": 16, "already_imported": 0, "problem_rows": 4}
    assert {p["row"]: p["messages"] for p in summary["problems"]} == {
        19: ["Date is not valid (use day/month/year, e.g. 15/03/2026)"],
        20: ["SKU ZZ-404 is not in your parts. Import it with “Parts and stock” first"],
        21: ["Quantity can't be 0"],
        22: ["Quantity is not a number"],
    }


def test_required_fields_must_be_matched(browser):
    set_up_shop(browser)
    mapping = {k: v for k, v in PARTS_MAPPING.items() if v != "name"}

    response = send(browser, "check", "parts", "parts_fr_messy.xlsx", mapping)

    assert response.status_code == 422
    assert response.json()["detail"] == "Choose a column for: Name."


def test_a_field_can_be_chosen_once(browser):
    set_up_shop(browser)

    response = send(browser, "check", "parts", "parts_fr_messy.xlsx", {**PARTS_MAPPING, 2: "name"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Name is chosen for two columns. Choose it for one column only."


# Files that can't be used


def test_file_problems(browser, monkeypatch):
    set_up_shop(browser)

    with monkeypatch.context() as small_limit:
        small_limit.setattr("app.imports.reading.MAX_FILE_BYTES", 1000)
        big = send(browser, "preview", "parts", "big.csv", content=b"SKU;Name\n" + b"A;" + b"x" * 1000)
    old_excel = send(browser, "preview", "parts", "stock.xls", content=b"whatever")
    pdf = send(browser, "preview", "parts", "stock.pdf", content=b"%PDF")
    broken = send(browser, "preview", "parts", "stock.xlsx", content=b"not really excel")
    empty = send(browser, "preview", "parts", "stock.csv", content=b"\n\n;;\n")
    header_only = send(browser, "preview", "parts", "stock.csv", content=b"SKU;Name\n")

    assert big.status_code == 413
    assert old_excel.json()["detail"] == "This is an old Excel file (.xls). Open it in Excel and save it as .xlsx."
    assert pdf.json()["detail"] == "Use an Excel file (.xlsx) or a CSV file (.csv)."
    assert broken.status_code == 422
    assert empty.json()["detail"] == "The file is empty."
    assert header_only.json()["detail"] == "The file has a header row but no data under it."


def test_file_with_too_many_rows_is_refused(browser, monkeypatch):
    set_up_shop(browser)
    monkeypatch.setattr("app.imports.reading.MAX_ROWS", 20)
    content = b"SKU;Name\n" + b"A;B\n" * 21

    response = send(browser, "preview", "parts", "huge.csv", content=content)

    assert response.status_code == 413
    assert response.json()["detail"] == "This file has more than 20 rows. Split it into smaller files."


# Step 4: save


def test_save_parts_creates_parts_stock_branches_suppliers(browser):
    set_up_shop(browser)

    summary = import_parts(browser)

    assert summary["counts"]["new_parts"] == 22
    assert count(Part) == 22
    assert count(Supplier) == 11
    with SessionLocal() as db:
        part = db.scalar(select(Part).where(Part.sku == "BT-912"))
        assert (part.name, part.unit_cost, part.sale_price, part.min_stock) == ("Batterie 12V 70Ah", 125000, 165000, 3)
        assert db.scalar(select(Part.sku).where(Part.sku == "BP-001")) == "BP-001"  # " bp-001 " cleaned
        assert sorted(db.scalars(select(Branch.name)).all()) == ["Atlas Parts", "Casablanca", "Rabat"]
        assert db.scalar(select(func.sum(StockLevel.quantity))) == 262  # all quantities in the file


def test_save_writes_one_audit_row_with_counts_and_file_name(browser):
    set_up_shop(browser)

    import_parts(browser)

    rows = audit_rows("import.saved")
    assert len(rows) == 1
    assert rows[0].after == {
        "kind": "parts",
        "file_name": "parts_fr_messy.xlsx",
        "new_parts": 22,
        "updated_parts": 0,
        "unchanged_parts": 0,
        "delivery_times": 0,
        "delivery_only": 0,
        "unread_delivery_times": 0,
        "problem_rows": 7,
        "new_suppliers": 11,
        "new_branches": 2,
    }


def test_update_keeps_values_the_file_leaves_empty(browser):
    set_up_shop(browser)
    import_parts(browser)
    content = "SKU;Quantity;Branch\nBP-001;9;Casablanca\n".encode()

    send(browser, "save", "parts", "stock.csv", {0: "sku", 1: "name", 2: "quantity"}, content=content)

    with SessionLocal() as db:
        part = db.scalar(select(Part).where(Part.sku == "BP-001"))
        assert part.name == "Plaquettes de frein avant"
        assert part.sale_price == 32000


def test_column_memory_adds_to_what_is_remembered_instead_of_replacing_it(browser):
    set_up_shop(browser)
    import_parts(browser)  # remembers all 11 headers of parts_fr_messy.xlsx

    # A different file (e.g. a quick supplier export) with headers never seen before.
    content = "Code;Qty\nBP-001;9\n".encode()
    send(browser, "save", "parts", "stock.csv", {0: "sku", 1: "quantity"}, content=content)

    # The first file's headers are still remembered, not wiped out by the second import.
    first_preview = send(browser, "preview", "parts", "parts_fr_messy.xlsx").json()
    assert {int(k): v for k, v in first_preview["mapping"].items()} == PARTS_MAPPING
    # And the new file's own headers are now remembered too.
    second_preview = send(browser, "preview", "parts", "stock.csv", content=content).json()
    assert {int(k): v for k, v in second_preview["mapping"].items()} == {0: "sku", 1: "quantity"}


def test_save_sales_and_import_again_without_doubling(browser):
    set_up_shop(browser)
    import_parts(browser)

    first = import_sales(browser)
    again = import_sales(browser)

    assert first["counts"]["new_sales"] == 16
    assert again["counts"] == {"new_sales": 0, "already_imported": 16, "problem_rows": 4}
    assert count(SaleLine) == 16


def test_big_clean_sales_file(browser):
    set_up_shop(browser)
    import_parts(browser)

    summary = import_sales(browser, "sales_en_clean.xlsx")

    assert summary["counts"] == {"new_sales": 270, "already_imported": 0, "problem_rows": 0}


def test_save_is_all_or_nothing(browser, monkeypatch):
    set_up_shop(browser)

    def fail(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.imports.jobs.record_change", fail)
    answer = send(browser, "save", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING)

    assert answer.json()["detail"] == NOTHING_SAVED
    assert count(Part) == 0
    assert count(Supplier) == 0
    assert count(StockLevel) == 0
    with SessionLocal() as db:
        assert db.scalars(select(Branch.name)).all() == ["Atlas Parts"]


# Who can import, and shop separation


def test_staff_cannot_import(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    for step in ["preview", "check", "save"]:
        assert send(staff, step, "parts", "parts_fr_messy.xlsx", PARTS_MAPPING).status_code == 403
    assert count(Part) == 0


def test_manager_can_import(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")

    assert import_parts(manager)["counts"]["new_parts"] == 22


def test_imports_stay_in_their_own_shop(browser):
    set_up_shop(browser)
    import_parts(browser)
    create_other_shop()
    other = logged_in_browser("owner@other.ma", OWNER_PASSWORD)

    summary = send(other, "check", "parts", "parts_fr_messy.xlsx", PARTS_MAPPING).json()
    import_parts(other)

    assert summary["counts"]["new_parts"] == 22  # the other shop's BP-001 is a new part for them
    assert count(Part) == 44
    assert send(other, "preview", "parts", "parts_fr_messy.xlsx").json()["mapping"] != {}
    with SessionLocal() as db:
        shops = db.execute(select(Part.organization_id, func.count()).group_by(Part.organization_id)).all()
    assert sorted(n for _, n in shops) == [22, 22]


# Pack size (optional column)


def test_pack_size_is_imported_when_the_file_has_it_and_is_1_otherwise(browser):
    set_up_shop(browser)
    content = "SKU;Name;Colisage\nOF-1;Oil filter;5\nBP-1;Brake pads;\n".encode()

    response = send(browser, "save", "parts", "packs.csv", {0: "sku", 1: "name", 2: "pack_size"}, content=content)

    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        packs = dict(db.execute(select(Part.sku, Part.pack_size)).all())
    assert packs == {"OF-1": 5, "BP-1": 1}


def test_pack_size_of_zero_is_a_problem_row(browser):
    set_up_shop(browser)
    content = "SKU;Name;Pack\nOF-1;Oil filter;0\nOF-2;Oil filter;2\n".encode()

    summary = send(browser, "save", "parts", "packs.csv", {0: "sku", 1: "name", 2: "pack_size"}, content=content).json()

    assert summary["counts"]["problem_rows"] == 1
    with SessionLocal() as db:
        assert dict(db.execute(select(Part.sku, Part.pack_size)).all()) == {"OF-2": 2}


# Sample files (Start here, empty states)


def test_sample_files_are_recognised_without_help(browser):
    from openpyxl import load_workbook
    from io import BytesIO

    from app.imports.fields import FIELDS

    set_up_shop(browser)  # the shop's language is French

    for kind in ("parts", "sales"):
        response = browser.get(f"/api/imports/sample?kind={kind}")
        assert response.status_code == 200, response.text
        workbook = load_workbook(BytesIO(response.content))
        assert workbook.active.max_row > 1

        preview = send(browser, "preview", kind, f"{kind}.xlsx", content=response.content).json()
        mapped_fields = set(preview["mapping"].values())
        required = {field.key for field in FIELDS[kind] if field.required}
        assert required <= mapped_fields, f"{kind}: {required - mapped_fields} not recognised without help"

        summary = send(browser, "save", kind, f"{kind}.xlsx", {int(k): v for k, v in preview["mapping"].items()}, content=response.content).json()
        assert summary["counts"]["problem_rows"] == 0


def test_there_is_no_sample_file_for_equivalents(browser):
    set_up_shop(browser)

    response = browser.get("/api/imports/sample?kind=equivalents")

    assert response.status_code == 404
