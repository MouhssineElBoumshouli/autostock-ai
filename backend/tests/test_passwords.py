from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog
from tests.helpers import (
    MEMBER_PASSWORD,
    OWN_MEMBER_PASSWORD,
    OWNER_PASSWORD,
    add_member,
    audit_rows,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    new_browser,
    set_up_shop,
)

NEW_PASSWORD = "brand-new-password-1"


def change(browser, current: str, new: str):
    return browser.post("/api/auth/password", json={"current_password": current, "new_password": new})


def login_status(email: str, password: str) -> int:
    return new_browser().post("/api/auth/login", json={"email": email, "password": password}).status_code


# Changing your own password


def test_change_own_password(browser):
    set_up_shop(browser)

    response = change(browser, OWNER_PASSWORD, NEW_PASSWORD)

    assert response.status_code == 200
    assert login_status("owner@shop.ma", OWNER_PASSWORD) == 401
    assert login_status("owner@shop.ma", NEW_PASSWORD) == 200


def test_wrong_current_password_is_rejected(browser):
    set_up_shop(browser)

    response = change(browser, "not-my-password", NEW_PASSWORD)

    assert response.status_code == 400
    assert response.json() == {"detail": "Your current password is wrong."}
    assert login_status("owner@shop.ma", OWNER_PASSWORD) == 200


def test_guessing_the_current_password_is_slowed_down(browser):
    set_up_shop(browser)
    for _ in range(5):
        change(browser, "not-my-password", NEW_PASSWORD)

    response = change(browser, OWNER_PASSWORD, NEW_PASSWORD)

    assert response.status_code == 429


def test_new_password_needs_10_characters(browser):
    set_up_shop(browser)

    assert change(browser, OWNER_PASSWORD, "short").status_code == 422


def test_new_password_must_be_different(browser):
    set_up_shop(browser)

    assert change(browser, OWNER_PASSWORD, OWNER_PASSWORD).status_code == 422


def test_changing_password_logs_out_other_sessions_but_not_this_one(browser):
    set_up_shop(browser)
    other_device = logged_in_browser("owner@shop.ma", OWNER_PASSWORD)

    change(browser, OWNER_PASSWORD, NEW_PASSWORD)

    assert browser.get("/api/auth/me").status_code == 200
    assert other_device.get("/api/auth/me").status_code == 401


def test_password_change_is_audited_without_the_password(browser):
    set_up_shop(browser)

    change(browser, OWNER_PASSWORD, NEW_PASSWORD)

    rows = audit_rows("user.password_changed")
    assert len(rows) == 1
    assert rows[0].before is None and rows[0].after is None


def test_changing_password_needs_login(browser):
    assert change(browser, OWNER_PASSWORD, NEW_PASSWORD).status_code == 401


# Forced change after the owner set the password


def test_new_person_must_choose_a_password_before_anything_else(browser):
    set_up_shop(browser)
    add_member(browser, "second@shop.ma", "owner")
    second = logged_in_browser("second@shop.ma", MEMBER_PASSWORD)

    me = second.get("/api/auth/me")
    blocked = second.get("/api/users")

    assert me.status_code == 200
    assert me.json()["user"]["must_change_password"] is True
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Choose a new password first."}

    assert change(second, MEMBER_PASSWORD, OWN_MEMBER_PASSWORD).status_code == 200
    assert second.get("/api/auth/me").json()["user"]["must_change_password"] is False
    assert second.get("/api/users").status_code == 200


def test_shop_founder_does_not_need_to_change_password(browser):
    me = set_up_shop(browser)

    assert me["user"]["must_change_password"] is False


# Owner resets someone's password


def test_owner_resets_a_password(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    response = browser.post(f"/api/users/{staff_member['id']}/password", json={"temporary_password": NEW_PASSWORD})

    assert response.status_code == 204
    assert staff.get("/api/auth/me").status_code == 401  # logged out everywhere
    assert login_status("staff@shop.ma", OWN_MEMBER_PASSWORD) == 401
    again = logged_in_browser("staff@shop.ma", NEW_PASSWORD)
    assert again.get("/api/auth/me").json()["user"]["must_change_password"] is True


def test_password_reset_is_audited_without_the_password(browser):
    me = set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")

    browser.post(f"/api/users/{staff_member['id']}/password", json={"temporary_password": NEW_PASSWORD})

    rows = audit_rows("user.password_reset")
    assert len(rows) == 1
    assert str(rows[0].user_id) == me["user"]["id"]
    assert str(rows[0].entity_id) == staff_member["id"]
    with SessionLocal() as db:
        everything = str([(row.before, row.after) for row in db.scalars(select(AuditLog))])
    assert NEW_PASSWORD not in everything


def test_staff_and_manager_cannot_reset_passwords(browser):
    me = set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    add_member(browser, "manager@shop.ma", "manager")

    for email in ["staff@shop.ma", "manager@shop.ma"]:
        member = member_with_own_password(email)
        for target in [me["user"]["id"], staff_member["id"]]:
            response = member.post(f"/api/users/{target}/password", json={"temporary_password": NEW_PASSWORD})
            assert response.status_code == 403
    assert login_status("owner@shop.ma", OWNER_PASSWORD) == 200


def test_owner_cannot_reset_another_shops_password(browser):
    set_up_shop(browser)
    other_owner = create_other_shop()

    response = browser.post(f"/api/users/{other_owner.id}/password", json={"temporary_password": NEW_PASSWORD})

    assert response.status_code == 404
    assert login_status("owner@other.ma", OWNER_PASSWORD) == 200


def test_owner_cannot_reset_own_password_from_the_team_page(browser):
    me = set_up_shop(browser)

    response = browser.post(f"/api/users/{me['user']['id']}/password", json={"temporary_password": NEW_PASSWORD})

    assert response.status_code == 409


def test_temporary_password_needs_10_characters(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")

    response = browser.post(f"/api/users/{staff_member['id']}/password", json={"temporary_password": "short"})

    assert response.status_code == 422
