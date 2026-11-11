from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog
from tests.helpers import (
    MEMBER_PASSWORD,
    OWNER_PASSWORD,
    add_member,
    audit_rows,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    new_browser,
    set_up_shop,
)


def test_owner_adds_and_lists_people(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    add_member(browser, "staff@shop.ma", "staff")

    people = browser.get("/api/users").json()

    assert [(person["email"], person["role"]) for person in people] == [
        ("owner@shop.ma", "owner"),
        ("manager@shop.ma", "manager"),
        ("staff@shop.ma", "staff"),
    ]
    assert all("password" not in person and "password_hash" not in person for person in people)
    assert "$argon2" not in str(people)


def test_new_person_can_log_in_with_temporary_password(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")

    staff = logged_in_browser("staff@shop.ma", MEMBER_PASSWORD)

    assert staff.get("/api/auth/me").json()["user"]["role"] == "staff"


def test_email_already_used_is_rejected(browser):
    set_up_shop(browser)

    response = browser.post(
        "/api/users",
        json={"name": "Copy", "email": "OWNER@shop.ma", "role": "staff", "temporary_password": MEMBER_PASSWORD},
    )

    assert response.status_code == 409


def test_temporary_password_needs_10_characters(browser):
    set_up_shop(browser)

    response = browser.post(
        "/api/users", json={"name": "Ali", "email": "ali@shop.ma", "role": "staff", "temporary_password": "123456789"}
    )

    assert response.status_code == 422


def test_staff_and_manager_cannot_manage_people(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    add_member(browser, "manager@shop.ma", "manager")

    for email in ["staff@shop.ma", "manager@shop.ma"]:
        member = member_with_own_password(email)
        assert member.get("/api/users").json() == {"detail": "Only the owner can do this."}
        new = {"name": "X", "email": "x@shop.ma", "role": "owner", "temporary_password": MEMBER_PASSWORD}
        assert member.post("/api/users", json=new).status_code == 403
        assert member.patch(f"/api/users/{staff_member['id']}", json={"role": "owner"}).status_code == 403


def test_not_logged_in_cannot_list_people(browser):
    set_up_shop(browser)

    assert new_browser().get("/api/users").status_code == 401


def test_owner_cannot_see_or_change_another_shops_people(browser):
    set_up_shop(browser)
    other_owner = create_other_shop()

    emails = [person["email"] for person in browser.get("/api/users").json()]
    response = browser.patch(f"/api/users/{other_owner.id}", json={"is_active": False})

    assert "owner@other.ma" not in emails
    assert response.status_code == 404


def test_owner_changes_a_role_and_it_is_audited(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")

    response = browser.patch(f"/api/users/{staff_member['id']}", json={"role": "manager"})

    assert response.json()["role"] == "manager"
    row = audit_rows("user.updated")[-1]
    assert row.before["role"] == "staff"
    assert row.after["role"] == "manager"


def test_deactivated_person_is_logged_out_and_cannot_log_in(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    staff = logged_in_browser("staff@shop.ma", MEMBER_PASSWORD)

    browser.patch(f"/api/users/{staff_member['id']}", json={"is_active": False})

    assert staff.get("/api/auth/me").status_code == 401
    response = new_browser().post("/api/auth/login", json={"email": "staff@shop.ma", "password": MEMBER_PASSWORD})
    assert response.status_code == 403
    assert response.json()["detail"] == "This account is deactivated. Ask your shop owner."


def test_reactivated_person_can_log_in_again(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    browser.patch(f"/api/users/{staff_member['id']}", json={"is_active": False})

    browser.patch(f"/api/users/{staff_member['id']}", json={"is_active": True})

    logged_in_browser("staff@shop.ma", MEMBER_PASSWORD)


def test_cannot_demote_or_deactivate_the_last_owner(browser):
    me = set_up_shop(browser)
    owner_id = me["user"]["id"]

    demote = browser.patch(f"/api/users/{owner_id}", json={"role": "manager"})
    deactivate = browser.patch(f"/api/users/{owner_id}", json={"is_active": False})

    assert demote.status_code == deactivate.status_code == 409
    assert demote.json()["detail"] == "The shop needs at least one owner. Make someone else owner first."
    assert browser.get("/api/auth/me").json()["user"]["role"] == "owner"


def test_an_owner_can_step_down_when_another_owner_exists(browser):
    me = set_up_shop(browser)
    add_member(browser, "second@shop.ma", "owner")

    response = browser.patch(f"/api/users/{me['user']['id']}", json={"role": "manager"})

    assert response.status_code == 200
    assert browser.get("/api/users").status_code == 403


def test_audit_log_never_contains_passwords(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    logged_in_browser("owner@shop.ma", OWNER_PASSWORD)

    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog)).all()
    text = str([(row.before, row.after) for row in rows])
    assert rows
    assert OWNER_PASSWORD not in text
    assert MEMBER_PASSWORD not in text
    assert "argon2" not in text
    assert "password" not in text
