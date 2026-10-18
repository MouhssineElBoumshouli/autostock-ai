from datetime import timedelta

from sqlalchemy import select, update

from app.auth.sessions import COOKIE_NAME
from app.db import SessionLocal, utc_now
from app.models import UserSession
from tests.helpers import OWNER_PASSWORD, logged_in_browser, new_browser, set_up_shop


def test_login_with_right_password(browser):
    set_up_shop(browser)
    other = new_browser()

    response = other.post("/api/auth/login", json={"email": "Owner@Shop.ma ", "password": OWNER_PASSWORD})

    assert response.status_code == 200
    assert response.json()["user"]["last_login_at"] is not None
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie  # running locally over http


def test_wrong_password_and_wrong_email_get_the_same_message(browser):
    set_up_shop(browser)
    other = new_browser()

    wrong_password = other.post("/api/auth/login", json={"email": "owner@shop.ma", "password": "wrong-password"})
    wrong_email = other.post("/api/auth/login", json={"email": "nobody@shop.ma", "password": OWNER_PASSWORD})

    assert wrong_password.status_code == wrong_email.status_code == 401
    assert wrong_password.json() == wrong_email.json() == {"detail": "Wrong email or password."}


def test_locked_out_after_5_wrong_tries_even_with_right_password(browser):
    set_up_shop(browser)
    other = new_browser()
    for _ in range(5):
        assert other.post("/api/auth/login", json={"email": "owner@shop.ma", "password": "wrong-pass"}).status_code == 401

    response = other.post("/api/auth/login", json={"email": "owner@shop.ma", "password": OWNER_PASSWORD})

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many tries. Wait 15 minutes."}


def test_unknown_email_is_locked_out_the_same_way(browser):
    for _ in range(5):
        browser.post("/api/auth/login", json={"email": "nobody@shop.ma", "password": "wrong-pass"})

    response = browser.post("/api/auth/login", json={"email": "nobody@shop.ma", "password": "wrong-pass"})

    assert response.status_code == 429


def test_me_needs_login(browser):
    response = browser.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Please log in."}


def test_logout_deletes_the_session(browser):
    set_up_shop(browser)
    token = browser.cookies[COOKIE_NAME]

    assert browser.post("/api/auth/logout").status_code == 204

    stolen = new_browser()
    stolen.cookies.set(COOKIE_NAME, token)
    assert stolen.get("/api/auth/me").status_code == 401
    with SessionLocal() as db:
        assert db.scalars(select(UserSession)).all() == []


def test_session_expires_after_7_days_without_use(browser):
    set_up_shop(browser)
    with SessionLocal() as db:
        db.execute(update(UserSession).values(last_used_at=utc_now() - timedelta(days=7, minutes=1)))
        db.commit()

    assert browser.get("/api/auth/me").status_code == 401


def test_session_used_within_7_days_stays_valid(browser):
    set_up_shop(browser)
    with SessionLocal() as db:
        db.execute(update(UserSession).values(last_used_at=utc_now() - timedelta(days=6)))
        db.commit()

    assert browser.get("/api/auth/me").status_code == 200
    with SessionLocal() as db:
        assert utc_now() - db.scalars(select(UserSession.last_used_at)).one() < timedelta(minutes=1)


def test_only_a_hash_of_the_token_is_stored(browser):
    set_up_shop(browser)
    token = browser.cookies[COOKIE_NAME]

    with SessionLocal() as db:
        stored = db.scalars(select(UserSession.token_hash)).one()
    assert stored != token
    assert len(stored) == 64


def test_login_with_another_browser_keeps_both_sessions(browser):
    set_up_shop(browser)
    second = logged_in_browser("owner@shop.ma", OWNER_PASSWORD)

    assert browser.get("/api/auth/me").status_code == 200
    assert second.get("/api/auth/me").status_code == 200
