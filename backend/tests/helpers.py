"""Shortcuts used by several test files."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.passwords import hash_password
from app.config import APP_URL
from app.db import SessionLocal
from app.main import app
from app.models import AuditLog, Branch, Organization, User

OWNER_PASSWORD = "owner-password-1"
MEMBER_PASSWORD = "member-password-1"
OWN_MEMBER_PASSWORD = "chosen-by-member-1"


def new_browser() -> TestClient:
    """A separate browser with its own cookies, sending requests from our website."""
    return TestClient(app, headers={"Origin": APP_URL})


def set_up_shop(browser: TestClient, email: str = "owner@shop.ma") -> dict:
    response = browser.post(
        "/api/setup",
        json={"shop_name": "Atlas Parts", "name": "Sara Owner", "email": email, "password": OWNER_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_member(owner: TestClient, email: str, role: str) -> dict:
    response = owner.post(
        "/api/users",
        json={"name": email.split("@")[0], "email": email, "role": role, "temporary_password": MEMBER_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def logged_in_browser(email: str, password: str) -> TestClient:
    browser = new_browser()
    response = browser.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return browser


def member_with_own_password(email: str) -> TestClient:
    """A new person who logged in and chose their own password, so nothing blocks them anymore."""
    browser = logged_in_browser(email, MEMBER_PASSWORD)
    response = browser.post(
        "/api/auth/password", json={"current_password": MEMBER_PASSWORD, "new_password": OWN_MEMBER_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return browser


def create_other_shop() -> User:
    """A second organization, made directly in the database (setup only works once)."""
    with SessionLocal() as db:
        organization = Organization(name="Other Shop")
        db.add(organization)
        db.flush()
        db.add(Branch(organization_id=organization.id, name="Other Shop"))
        owner = User(
            organization_id=organization.id,
            name="Other Owner",
            email="owner@other.ma",
            password_hash=hash_password(OWNER_PASSWORD),
            role="owner",
        )
        db.add(owner)
        db.commit()
        return owner


def audit_rows(action: str) -> list[AuditLog]:
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)))


def run_lines(browser: TestClient, run: dict) -> list[dict]:
    """Every line of an order run, group after group, the way the What to order screen reads them."""
    lines = []
    for group in run["groups"]:
        page = 1
        while True:
            response = browser.get(f"/api/orders/runs/{run['id']}/lines", params={"group": group["key"], "page": page})
            assert response.status_code == 200, response.text
            lines += response.json()["items"]
            if page * response.json()["page_size"] >= response.json()["total"]:
                break
            page += 1
    return lines
