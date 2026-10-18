"""Shortcuts used by several test files."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.passwords import hash_password
from app.config import APP_URL
from app.db import SessionLocal
from app.main import app
from app.models import AuditLog, Organization, User

OWNER_PASSWORD = "owner-password-1"
MEMBER_PASSWORD = "member-password-1"


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


def create_other_shop() -> User:
    """A second organization, made directly in the database (setup only works once)."""
    with SessionLocal() as db:
        organization = Organization(name="Other Shop")
        db.add(organization)
        db.flush()
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
