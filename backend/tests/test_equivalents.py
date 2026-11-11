"""Equivalent parts: same OEM number (automatic), a manager's link, a supplier's cross-reference
file, grouping (A=B and B=C means A=C), permissions, and shop separation."""

from app.search.default_synonyms import DEFAULT_SYNONYMS
from tests.helpers import (
    OWNER_PASSWORD,
    add_member,
    audit_rows,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    set_up_shop,
)
from tests.import_helpers import send

PART_MAPPING = {0: "sku", 1: "name", 2: "brand", 3: "oem_reference", 4: "quantity", 5: "branch"}
EQUIVALENT_MAPPING = {0: "our_code", 1: "equivalent_code"}


def import_part_rows(browser, rows: list[tuple[str, str, str, str, int, str]]) -> dict:
    header = "SKU;Name;Brand;OEM;Quantity;Branch"
    lines = [";".join([sku, name, brand, oem, str(quantity), branch]) for sku, name, brand, oem, quantity, branch in rows]
    content = "\n".join([header, *lines, ""]).encode()
    response = send(browser, "save", "parts", "parts.csv", PART_MAPPING, content=content)
    assert response.status_code == 200, response.text
    return response.json()


def part_id(browser, sku: str) -> str:
    response = browser.get("/api/stock/parts", params={"search": sku})
    assert response.status_code == 200, response.text
    [item] = [i for i in response.json()["items"] if i["sku"] == sku]
    return item["id"]


def equivalents(browser, sku: str) -> dict:
    response = browser.get(f"/api/parts/{part_id(browser, sku)}")
    assert response.status_code == 200, response.text
    return {e["sku"]: e for e in response.json()["equivalents"]}


def shop_with_two_brands(browser):
    """Two parts, same OEM number written differently - so they are automatic equivalents."""
    set_up_shop(browser)
    import_part_rows(
        browser,
        [
            ("BP-001", "Brake pads front", "Bosch", "0 986-424.815", 0, "Main"),
            ("TRW-220", "Brake pads front", "TRW", "0986424815", 6, "Main"),
        ],
    )


# Automatic: same OEM number


def test_same_oem_number_is_an_automatic_equivalent(browser):
    shop_with_two_brands(browser)

    found = equivalents(browser, "BP-001")

    assert found["TRW-220"]["reason_type"] == "oem"
    assert found["TRW-220"]["link_id"] is None
    assert found["TRW-220"]["brand"] == "TRW"
    assert found["TRW-220"]["in_stock"] is True
    assert found["TRW-220"]["quantity"] == 6
    # "Atlas Parts" (the shop's default branch, never used since everything came in under "Main") is left out.
    assert {row["branch"]: row["quantity"] for row in found["TRW-220"]["stock"]} == {"Main": 6}
    # Symmetric
    assert equivalents(browser, "TRW-220")["BP-001"]["reason_type"] == "oem"


def test_three_parts_with_the_same_oem_number_all_group_together(browser):
    shop_with_two_brands(browser)
    import_part_rows(browser, [("GB-9", "Brake pads front", "Gabriel", "0986424815", 2, "Main")])

    found = equivalents(browser, "BP-001")

    assert {"TRW-220", "GB-9"} <= found.keys()


def test_in_stock_equivalents_are_listed_first(browser):
    set_up_shop(browser)
    import_part_rows(
        browser,
        [
            ("A-1", "Part A", "BrandA", "SAME-CODE", 0, "Main"),
            ("B-1", "Part B", "BrandB", "SAME-CODE", 0, "Main"),
            ("C-1", "Part C", "BrandC", "SAME-CODE", 3, "Main"),
        ],
    )

    response = browser.get(f"/api/parts/{part_id(browser, 'A-1')}")
    skus = [e["sku"] for e in response.json()["equivalents"]]

    assert skus[0] == "C-1"  # the only one in stock comes first


# Manual links


def test_manager_can_link_two_parts_by_hand(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    a, b = part_id(browser, "AA-1"), part_id(browser, "BB-1")

    response = browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b})

    assert response.status_code == 200, response.text
    found = {e["sku"]: e for e in response.json()["equivalents"]}
    assert found["BB-1"]["reason_type"] == "manual"
    assert found["BB-1"]["linked_by"] == "Sara Owner"
    assert found["BB-1"]["link_id"] is not None
    # Symmetric
    assert equivalents(browser, "BB-1")["AA-1"]["reason_type"] == "manual"

    rows = audit_rows("part_equivalent.linked")
    assert len(rows) == 1
    assert rows[0].after == {"part": "Oil filter (AA-1)", "other_part": "Oil filter (BB-1)", "source": "manual"}


def test_a_part_cannot_be_its_own_equivalent(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main")])
    a = part_id(browser, "AA-1")

    response = browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": a})

    assert response.status_code == 422


def test_the_same_pair_cannot_be_linked_twice(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    a, b = part_id(browser, "AA-1"), part_id(browser, "BB-1")
    browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b})

    response = browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b})

    assert response.status_code == 422
    assert response.json()["detail"] == "These parts are already linked."


def test_manager_can_remove_a_wrong_link(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    a, b = part_id(browser, "AA-1"), part_id(browser, "BB-1")
    link_id = browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b}).json()["equivalents"][0]["link_id"]

    response = browser.delete(f"/api/parts/{a}/equivalents/{link_id}")

    assert response.status_code == 200, response.text
    assert response.json()["equivalents"] == []
    rows = audit_rows("part_equivalent.removed")
    assert len(rows) == 1
    assert rows[0].before == {"part": "Oil filter (AA-1)", "other_part": "Oil filter (BB-1)", "source": "manual"}


def test_removing_an_unknown_link_is_404(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main")])
    a = part_id(browser, "AA-1")

    response = browser.delete(f"/api/parts/{a}/equivalents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_staff_can_see_but_not_change_links(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    a, b = part_id(browser, "AA-1"), part_id(browser, "BB-1")
    link_id = browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b}).json()["equivalents"][0]["link_id"]
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    assert staff.get(f"/api/parts/{a}").json()["equivalents"][0]["sku"] == "BB-1"  # can see
    assert staff.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b}).status_code == 403
    assert staff.delete(f"/api/parts/{a}/equivalents/{link_id}").status_code == 403


# Grouping: if A = B and B = C, then A = C


def test_equivalents_group_transitively(browser):
    set_up_shop(browser)
    import_part_rows(
        browser,
        [
            ("A-1", "Oil filter", "Bosch", "", 0, "Main"),
            ("B-1", "Oil filter", "Mann", "SAME-CODE", 0, "Main"),
            ("C-1", "Oil filter", "Fram", "SAME-CODE", 5, "Main"),
        ],
    )
    a, b = part_id(browser, "A-1"), part_id(browser, "B-1")
    browser.post(f"/api/parts/{a}/equivalents", json={"other_part_id": b})  # A - B manual, B - C same OEM

    found = equivalents(browser, "A-1")

    assert {"B-1", "C-1"} <= found.keys()


# Shop separation


def test_equivalents_stay_in_their_own_shop(browser):
    shop_with_two_brands(browser)
    create_other_shop()
    other = logged_in_browser("owner@other.ma", OWNER_PASSWORD)
    import_part_rows(
        other,
        [
            ("BP-001", "Brake pads front", "Bosch", "0986424815", 0, "Main"),
            ("TRW-220", "Brake pads front", "TRW", "0986424815", 9, "Main"),
        ],
    )

    assert equivalents(browser, "BP-001")["TRW-220"]["quantity"] == 6  # not the other shop's 9


# Cross-reference file import


def send_equivalents(browser, step: str, content: bytes):
    return send(browser, step, "equivalents", "cross_ref.csv", EQUIVALENT_MAPPING, content=content)


def test_cross_reference_file_links_our_parts(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    content = b"Our code;Equivalent code\nAA-1;BB-1\n"

    summary = send_equivalents(browser, "save", content).json()

    assert summary["counts"] == {"new_equivalents": 1, "already_linked": 0, "problem_rows": 0}
    found = equivalents(browser, "AA-1")
    assert found["BB-1"]["reason_type"] == "supplier_file"
    assert found["BB-1"]["link_id"] is not None


def test_cross_reference_codes_ignore_spaces_dashes_and_dots(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA 001", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    content = "Our code;Equivalent code\naa.001;bb1\n".encode()

    summary = send_equivalents(browser, "save", content).json()

    assert summary["counts"]["new_equivalents"] == 1


def test_cross_reference_unknown_code_is_a_problem_row(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main")])
    content = b"Our code;Equivalent code\nAA-1;ZZ-404\n"

    summary = send_equivalents(browser, "check", content).json()

    assert summary["counts"] == {"new_equivalents": 0, "already_linked": 0, "problem_rows": 1}
    assert summary["problems"][0]["messages"] == [
        "Equivalent code “ZZ-404” is not one of your parts"
    ]


def test_importing_the_same_cross_reference_file_twice_does_not_duplicate(browser):
    set_up_shop(browser)
    import_part_rows(browser, [("AA-1", "Oil filter", "Bosch", "", 0, "Main"), ("BB-1", "Oil filter", "Mann", "", 4, "Main")])
    content = b"Our code;Equivalent code\nAA-1;BB-1\n"
    send_equivalents(browser, "save", content)

    summary = send_equivalents(browser, "save", content).json()

    assert summary["counts"] == {"new_equivalents": 0, "already_linked": 1, "problem_rows": 0}
    assert len(equivalents(browser, "AA-1")) == 1


def test_staff_cannot_import_equivalents(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    assert send_equivalents(staff, "save", b"Our code;Equivalent code\nAA-1;BB-1\n").status_code == 403


# Stock search: an out-of-stock part shows the nearest in-stock equivalent


def test_out_of_stock_part_shows_an_in_stock_equivalent_in_the_stock_list(browser):
    shop_with_two_brands(browser)

    response = browser.get("/api/stock/parts", params={"search": "BP-001"})

    [row] = [item for item in response.json()["items"] if item["sku"] == "BP-001"]
    assert row["status"] == "out"
    assert row["equivalent_note"] == {"quantity": 6, "brand": "TRW"}


def test_in_stock_part_has_no_equivalent_note(browser):
    shop_with_two_brands(browser)

    response = browser.get("/api/stock/parts", params={"search": "TRW-220"})

    [row] = [item for item in response.json()["items"] if item["sku"] == "TRW-220"]
    assert row["equivalent_note"] is None


# Default search words


def test_default_brake_pads_words_include_the_darija_term():
    [brake_pads_group] = [group for group in DEFAULT_SYNONYMS if "brake pads" in group]
    assert "وسادات الفرامل" in brake_pads_group
