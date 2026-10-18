from app.audit import record_change
from app.db import SessionLocal
from app.models import User
from tests.helpers import (
    OWNER_PASSWORD,
    add_member,
    create_other_shop,
    logged_in_browser,
    member_with_own_password,
    new_browser,
    set_up_shop,
)


def actions(page: dict) -> list[str]:
    return [item["action"] for item in page["items"]]


def test_owner_sees_activity_newest_first(browser):
    set_up_shop(browser)
    staff_member = add_member(browser, "staff@shop.ma", "staff")
    browser.patch(f"/api/users/{staff_member['id']}", json={"role": "manager"})

    page = browser.get("/api/activity").json()

    # Setup writes one line ("created the shop"), then adding and changing the person.
    assert actions(page) == ["user.updated", "user.created", "organization.created"]
    newest = page["items"][0]
    assert newest["actor"]["name"] == "Sara Owner"
    assert newest["target"]["name"] == "staff"
    assert newest["before"]["role"] == "staff"
    assert newest["after"]["role"] == "manager"


def test_manager_can_read_activity(browser):
    set_up_shop(browser)
    add_member(browser, "manager@shop.ma", "manager")
    manager = member_with_own_password("manager@shop.ma")

    assert manager.get("/api/activity").status_code == 200
    assert manager.get("/api/activity/people").status_code == 200


def test_staff_cannot_read_activity(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")

    assert staff.get("/api/activity").status_code == 403
    assert staff.get("/api/activity/people").status_code == 403


def test_not_logged_in_cannot_read_activity(browser):
    set_up_shop(browser)

    assert new_browser().get("/api/activity").status_code == 401


def test_one_shop_cannot_see_another_shops_activity(browser):
    set_up_shop(browser)
    other_owner = create_other_shop()
    with SessionLocal() as db:
        actor = db.get_one(User, other_owner.id)
        record_change(db, actor, "user.updated", "user", actor.id, before={"role": "owner"}, after={"role": "owner"})
        db.commit()
    other = logged_in_browser("owner@other.ma", OWNER_PASSWORD)

    mine = browser.get("/api/activity").json()
    theirs = other.get("/api/activity").json()
    filtered = browser.get(f"/api/activity?person={other_owner.id}").json()

    assert all(item["actor"]["name"] == "Sara Owner" for item in mine["items"])
    assert all(item["actor"]["name"] == "Other Owner" for item in theirs["items"])
    assert filtered["total"] == 0
    assert "Other Owner" not in [person["name"] for person in browser.get("/api/activity/people").json()]


def test_filter_by_person(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    staff = member_with_own_password("staff@shop.ma")
    staff_id = staff.get("/api/auth/me").json()["user"]["id"]

    page = browser.get(f"/api/activity?person={staff_id}").json()

    assert actions(page) == ["user.password_changed", "user.logged_in"]


def test_filter_by_type_of_change(browser):
    set_up_shop(browser)
    add_member(browser, "staff@shop.ma", "staff")
    member_with_own_password("staff@shop.ma")

    assert actions(browser.get("/api/activity?kind=passwords").json()) == ["user.password_changed"]
    assert actions(browser.get("/api/activity?kind=logins").json()) == ["user.logged_in"]
    assert actions(browser.get("/api/activity?kind=settings").json()) == ["organization.created"]
    assert set(actions(browser.get("/api/activity?kind=team").json())) == {"user.created"}
    assert browser.get("/api/activity?kind=nonsense").status_code == 422


def test_25_per_page(browser):
    me = set_up_shop(browser)
    with SessionLocal() as db:
        owner = db.get_one(User, me["user"]["id"])
        for _ in range(30):
            record_change(db, owner, "user.logged_in", "user", owner.id)
        db.commit()

    first = browser.get("/api/activity").json()
    second = browser.get("/api/activity?page=2").json()

    assert first["total"] == 31
    assert len(first["items"]) == 25
    assert len(second["items"]) == 6
    assert first["page_size"] == 25
    assert {item["id"] for item in first["items"]}.isdisjoint(item["id"] for item in second["items"])


def test_activity_never_shows_passwords(browser):
    me = set_up_shop(browser)
    with SessionLocal() as db:
        owner = db.get_one(User, me["user"]["id"])
        record_change(db, owner, "user.updated", "user", owner.id, after={"role": "owner", "password_hash": "$argon2-x"})
        db.commit()

    text = browser.get("/api/activity").text

    assert "password_hash" not in text
    assert "$argon2" not in text
    assert OWNER_PASSWORD not in text
