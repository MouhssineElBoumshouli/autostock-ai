from tests.helpers import add_member, member_with_own_password, set_up_shop
from tests.import_helpers import PARTS_MAPPING, SALES_MAPPING, import_parts, import_sales


def steps(browser) -> dict[str, bool]:
    body = browser.get("/api/start-here").json()
    return {step["key"]: step["done"] for step in body["steps"]}


def test_a_brand_new_shop_has_nothing_checked_off(browser):
    set_up_shop(browser)

    body = browser.get("/api/start-here").json()

    assert body["hidden"] is False
    assert body["all_done"] is False
    assert steps(browser) == {
        "branches": False, "import_parts": False, "import_sales": False, "suppliers": False, "team": False,
    }


def test_importing_parts_and_sales_checks_off_those_steps(browser):
    set_up_shop(browser)
    import_parts(browser)
    import_sales(browser)

    assert steps(browser)["import_parts"] is True
    assert steps(browser)["import_sales"] is True
    # Importing parts also creates the branches and suppliers named in the file.
    assert steps(browser)["branches"] is True


def test_renaming_the_only_branch_checks_off_that_step(browser):
    set_up_shop(browser)
    branch_id = browser.get("/api/branches").json()[0]["id"]

    browser.patch(f"/api/branches/{branch_id}", json={"name": "Main warehouse"})

    assert steps(browser)["branches"] is True


def test_a_supplier_only_counts_once_it_has_a_delivery_time(browser):
    set_up_shop(browser)

    response = browser.post("/api/suppliers", json={"name": "Atlas Distribution"})
    assert response.status_code == 201, response.text
    assert steps(browser)["suppliers"] is False

    supplier_id = response.json()["id"]
    browser.patch(f"/api/suppliers/{supplier_id}/details", json={"delivery_days": 5})

    assert steps(browser)["suppliers"] is True


def test_inviting_someone_checks_off_the_team_step(browser):
    set_up_shop(browser)

    add_member(browser, "manager@shop.ma", "manager")

    assert steps(browser)["team"] is True


def test_hiding_the_checklist_persists(browser):
    set_up_shop(browser)

    response = browser.patch("/api/start-here", json={"hidden": True})
    assert response.json()["hidden"] is True

    assert browser.get("/api/start-here").json()["hidden"] is True


def test_staff_cannot_see_the_checklist(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    assert staff.get("/api/start-here").status_code == 403
