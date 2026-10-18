from tests.helpers import OWNER_PASSWORD, audit_rows, set_up_shop


def test_setup_is_needed_on_an_empty_install(browser):
    assert browser.get("/api/setup").json() == {"needed": True}


def test_setup_creates_shop_and_owner_and_logs_in(browser):
    me = set_up_shop(browser)

    assert me["organization"]["name"] == "Atlas Parts"
    assert me["user"]["role"] == "owner"
    assert me["user"]["email"] == "owner@shop.ma"
    assert browser.get("/api/auth/me").status_code == 200
    assert browser.get("/api/setup").json() == {"needed": False}


def test_setup_cannot_run_twice(browser):
    set_up_shop(browser)

    response = browser.post(
        "/api/setup",
        json={"shop_name": "Takeover", "name": "Eve", "email": "eve@evil.ma", "password": "eve-password-1"},
    )

    assert response.status_code == 409
    assert browser.post("/api/auth/login", json={"email": "eve@evil.ma", "password": "eve-password-1"}).status_code == 401


def test_setup_rejects_short_password(browser):
    response = browser.post(
        "/api/setup", json={"shop_name": "Atlas", "name": "Sara", "email": "sara@shop.ma", "password": "short"}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Use at least 10 characters for the password."


def test_setup_rejects_invalid_email(browser):
    response = browser.post(
        "/api/setup", json={"shop_name": "Atlas", "name": "Sara", "email": "not-an-email", "password": OWNER_PASSWORD}
    )

    assert response.status_code == 422


def test_setup_writes_audit_rows_without_password(browser):
    set_up_shop(browser)

    created = audit_rows("user.created")
    assert len(created) == 1
    assert created[0].after == {"name": "Sara Owner", "email": "owner@shop.ma", "role": "owner", "is_active": True}
    assert len(audit_rows("organization.created")) == 1
