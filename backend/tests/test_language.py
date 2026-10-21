from tests.helpers import add_member, member_with_own_password, new_browser, set_up_shop


def test_people_follow_the_shop_language_until_they_choose_their_own(browser):
    set_up_shop(browser)

    me = browser.get("/api/auth/me").json()
    assert me["organization"]["language"] == "fr"
    assert me["user"]["language"] is None

    me = browser.put("/api/auth/language", json={"language": "ar"}).json()
    assert me["user"]["language"] == "ar"
    assert browser.get("/api/auth/me").json()["user"]["language"] == "ar"

    me = browser.put("/api/auth/language", json={"language": None}).json()
    assert me["user"]["language"] is None


def test_staff_choose_their_own_language_without_changing_anyone_else(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    assert staff.put("/api/auth/language", json={"language": "en"}).status_code == 200

    assert staff.get("/api/auth/me").json()["user"]["language"] == "en"
    assert browser.get("/api/auth/me").json()["user"]["language"] is None


def test_unknown_language_is_rejected_and_login_is_needed(browser):
    set_up_shop(browser)

    assert browser.put("/api/auth/language", json={"language": "de"}).status_code == 422
    assert new_browser().put("/api/auth/language", json={"language": "fr"}).status_code == 401
